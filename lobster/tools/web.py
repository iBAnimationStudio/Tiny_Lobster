import os
import re
import json
import socket
import ipaddress
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, Any, List, Tuple
from curl_cffi import requests
from lobster.tools.base import Tool
from lobster.config import Config

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_EXTRACTED_CHARS = 4000

BOT_CHALLENGE_PATTERNS = [
    r"making sure you're not a bot",
    r"just a moment\.\.\.",
    r"protected by anubis",
    r"cf-browser-verification",
    r"turnstile",
    r"attention required! \| cloudflare",
    r"checking your browser",
    r"ddos-guard"
]


def is_safe_ip(ip_str: str) -> bool:
    """Check if an IP string belongs to private, loopback, or reserved space."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except ValueError:
        return False


def is_safe_url(url_str: str) -> Tuple[bool, str]:
    """Validate protocol and perform DNS resolution checks against SSRF."""
    try:
        parsed = urllib.parse.urlparse(url_str.strip())
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed."

        hostname = parsed.hostname
        if not hostname or hostname.lower() in ("localhost", "0.0.0.0"):
            return False, "Access to localhost is prohibited."

        try:
            for item in socket.getaddrinfo(hostname, None):
                if not is_safe_ip(item[4][0]):
                    return False, f"Blocked target private/local IP: {item[4][0]}"
        except socket.gaierror:
            return False, f"DNS resolution failed for hostname: {hostname}"

        return True, ""
    except Exception as e:
        return False, f"URL error: {str(e)}"


class CleanTextExtractor(HTMLParser):
    """Parses static HTML safely into clean plain text for the agent."""
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "iframe", "head", "canvas"}
    BLOCK_TAGS = {"p", "div", "article", "section", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
    HEADING_MAP = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.ignore_depth = 0
        self.chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: list):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth > 0:
            return

        if tag == "title":
            self.in_title = True
        elif tag in self.HEADING_MAP:
            self.chunks.append(f"\n\n{self.HEADING_MAP[tag]}")
        elif tag in self.BLOCK_TAGS or tag == "br":
            self.chunks.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return
        if self.ignore_depth > 0:
            return

        if tag == "title":
            self.in_title = False
        elif tag in self.BLOCK_TAGS or tag in self.HEADING_MAP:
            self.chunks.append("\n")

    def handle_data(self, data: str):
        if self.ignore_depth > 0:
            return
        if self.in_title:
            self.title += data.strip()
        else:
            self.chunks.append(data)

    def get_clean_text(self) -> str:
        raw = "".join(self.chunks)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        clean = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        return clean


class WebTool(Tool):
    name = "web"
    description = (
        "Search the web or fetch/extract readable text content from URLs. "
        "Use 'search' to find URLs and 'fetch' to read full article contents."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "fetch"],
                "description": "The web action: 'search' to query engines or 'fetch' to scrape a URL."
            },
            "query": {
                "type": "string",
                "description": "Search keywords (required if action='search')."
            },
            "url": {
                "type": "string",
                "description": "The full HTTP/HTTPS URL to read (required if action='fetch')."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (default: 5, max: 10)."
            }
        },
        "required": ["action"]
    }

    def __init__(self, config: Config):
        self.config = config

    def execute(self, action: str, query: str = None, url: str = None, limit: int = 5, **kwargs) -> str:
        try:
            if action == "search":
                if not query or not query.strip():
                    return "Error: 'query' parameter is required for web search."
                return self._search(query.strip(), max(1, min(limit or 5, 10)))

            elif action == "fetch":
                if not url or not url.strip():
                    return "Error: 'url' parameter is required to fetch a webpage."
                return self._fetch(url.strip())

            return f"Error: Unknown action '{action}'. Use 'search' or 'fetch'."
        except Exception as e:
            return f"Error in web tool execution: {str(e)}"

    def _clean_ddg_url(self, raw_url: str) -> str:
        if "uddg=" in raw_url:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
            return parsed.get("uddg", [raw_url])[0]
        return raw_url

    def _search_ddg_html(self, query: str, limit: int) -> List[Dict[str, str]]:
        endpoints = [
            ("https://html.duckduckgo.com/html/", {"q": query, "b": ""}),
            ("https://lite.duckduckgo.com/lite/", {"q": query})
        ]

        for endpoint, payload in endpoints:
            try:
                resp = requests.post(endpoint, data=payload, impersonate="chrome124", timeout=8)
                if resp.status_code != 200:
                    continue

                links = re.findall(
                    r'<a[^>]+class="[^"]*(?:result__a|result-link)[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    resp.text,
                    re.DOTALL
                )
                snippets = re.findall(
                    r'<(?:a|td|div)[^>]+class="[^"]*(?:result__snippet|result-snippet)[^"]*"[^>]*>(.*?)</(?:a|td|div)>',
                    resp.text,
                    re.DOTALL
                )

                if not links:
                    continue

                results = []
                for i in range(min(len(links), limit)):
                    raw_url, raw_title = links[i]
                    final_url = self._clean_ddg_url(raw_url)
                    title = re.sub(r"<[^>]+>", "", raw_title).strip()
                    snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else "No snippet."
                    
                    domain = urllib.parse.urlparse(final_url).netloc
                    if "duckduckgo.com" not in domain:
                        results.append({
                            "title": title or "Untitled",
                            "url": final_url,
                            "domain": domain,
                            "snippet": snippet
                        })

                if results:
                    return results
            except Exception:
                continue
        return []

    def _search(self, query: str, limit: int) -> str:
        results = self._search_ddg_html(query, limit)

        # Simplify query if exact phrasing returned nothing
        if not results:
            simplified = re.sub(r"\b(official|website|repository|page|site|webpage)\b", "", query, flags=re.I)
            simplified = re.sub(r"\s+", " ", simplified).strip()
            if simplified and simplified.lower() != query.lower():
                results = self._search_ddg_html(simplified, limit)

        # Wikipedia OpenSearch fallback
        if not results:
            try:
                wiki_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={limit}&namespace=0&format=json"
                resp = requests.get(wiki_url, impersonate="chrome124", timeout=6)
                data = resp.json()
                for i in range(min(len(data[3]), limit)):
                    results.append({
                        "title": data[1][i],
                        "url": data[3][i],
                        "domain": "en.wikipedia.org",
                        "snippet": data[2][i] or "Wikipedia entry."
                    })
            except Exception:
                pass

        if not results:
            return f"No search results found for: '{query}'."

        output = [f"### Web Search Results for: \"{query}\"\n"]
        for idx, r in enumerate(results[:limit], start=1):
            output.append(f"{idx}. **{r['title']}**\n   - **URL:** {r['url']}\n   - **Source:** {r['domain']}\n   - **Snippet:** {r['snippet']}\n")

        return "\n".join(output).strip()

    def _fetch(self, target_url: str) -> str:
        safe, reason = is_safe_url(target_url)
        if not safe:
            return f"Error: {reason}"

        try:
            resp = requests.get(
                target_url,
                impersonate="chrome124",
                timeout=12
            )

            # SSRF check on final URL after redirects
            if resp.url != target_url:
                safe, reason = is_safe_url(resp.url)
                if not safe:
                    return f"Error: Redirect blocked: {reason}"

            if resp.status_code >= 400:
                return f"Fetch HTTP Error {resp.status_code}: {resp.reason}"

            html_content = resp.text

            # Fail cleanly on interactive bot challenges instead of feeding junk to the LLM
            is_bot_page = any(re.search(pat, html_content, re.IGNORECASE) for pat in BOT_CHALLENGE_PATTERNS)
            if is_bot_page:
                return (
                    f"Notice: The website at {resp.url} requires interactive browser verification "
                    "(Cloudflare Turnstile, Anubis, or DDoS-Guard). Content cannot be extracted via direct HTTP. "
                    "Please refer to the search snippets or query an alternative source URL."
                )

            parser = CleanTextExtractor()
            parser.feed(html_content)
            extracted_text = parser.get_clean_text()
            title = parser.title or "Untitled Document"

            if not extracted_text:
                return f"Notice: No readable text content could be extracted from {target_url}."

            is_truncated = False
            if len(extracted_text) > MAX_EXTRACTED_CHARS:
                extracted_text = extracted_text[:MAX_EXTRACTED_CHARS]
                is_truncated = True

            output = [
                "---",
                f"**Page Title:** {title}",
                f"**URL:** {resp.url}",
                "---",
                "<untrusted_web_content>",
                extracted_text,
                "</untrusted_web_content>"
            ]

            if is_truncated:
                output.append("\n[Content truncated to stay within context limits]")

            return "\n".join(output)

        except Exception as e:
            return f"Error fetching webpage: {str(e)}"
