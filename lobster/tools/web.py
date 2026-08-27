import os
import re
import json
import ipaddress
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser
from typing import Dict, Any, List, Tuple
from lobster.tools.base import Tool
from lobster.config import Config

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MAX_DOWNLOAD_BYTES = 1024 * 1024  # 1 MB
MAX_EXTRACTED_CHARS = 4000        # Context limit


def is_safe_url(url_str: str) -> Tuple[bool, str]:
    """Validate URL protocol and block loopback/private SSRF targets."""
    try:
        parsed = urllib.parse.urlparse(url_str.strip())
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed."
        
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: Missing hostname."

        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False, "Access to localhost/loopback addresses is prohibited."

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"Access to private/local IP address '{hostname}' is blocked."
        except ValueError:
            pass

        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


class CleanTextExtractor(HTMLParser):
    """Strips HTML boilerplate and extracts clean readable text."""
    IGNORE_TAGS = {
        "script", "style", "noscript", "svg", "header", 
        "footer", "nav", "iframe", "head", "link", "meta"
    }
    BLOCK_TAGS = {"p", "div", "article", "section", "li", "tr", "blockquote"}
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

    def _clean_url(self, raw_url: str) -> str:
        """Decode DuckDuckGo redirect wrapper URLs."""
        if "uddg=" in raw_url:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
            return parsed.get("uddg", [raw_url])[0]
        if raw_url.startswith("//"):
            return "https:" + raw_url
        return raw_url

    def _fetch_ddg_html(self, query: str) -> str:
        """Fetch search results via POST to avoid GET bot-blocks."""
        endpoints = [
            ("https://html.duckduckgo.com/html/", {"q": query, "b": ""}),
            ("https://lite.duckduckgo.com/lite/", {"q": query})
        ]

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://duckduckgo.com",
            "Referer": "https://duckduckgo.com/"
        }

        for url, form_data in endpoints:
            try:
                data = urllib.parse.urlencode(form_data).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    if "result__snippet" in raw or "result-snippet" in raw:
                        return raw
            except Exception:
                continue

        # Fallback to standard GET if POST failed
        fallback_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(fallback_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _search(self, query: str, limit: int) -> str:
        try:
            raw_html = self._fetch_ddg_html(query)
            results = []

            # 1. Try DuckDuckGo HTML format
            link_pattern = re.findall(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                raw_html,
                re.DOTALL
            )
            snippet_pattern = re.findall(
                r'<(?:a|td|div)[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|td|div)>',
                raw_html,
                re.DOTALL
            )

            # 2. Try DuckDuckGo Lite format if HTML format was empty
            if not link_pattern:
                link_pattern = re.findall(
                    r'<a[^>]+class="[^"]*result-link[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    raw_html,
                    re.DOTALL
                )
                snippet_pattern = re.findall(
                    r'<td[^>]+class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>',
                    raw_html,
                    re.DOTALL
                )

            count = min(len(link_pattern), limit)
            for i in range(count):
                raw_href, raw_title = link_pattern[i]
                url = self._clean_url(raw_href)
                title = re.sub(r'<[^>]+>', '', raw_title).strip()
                domain = urllib.parse.urlparse(url).netloc
                
                snippet = "No snippet available."
                if i < len(snippet_pattern):
                    snippet = re.sub(r'<[^>]+>', '', snippet_pattern[i]).strip()

                results.append({
                    "title": title or "Untitled",
                    "url": url,
                    "domain": domain,
                    "snippet": snippet
                })

            if not results:
                return f"No search results found for query: '{query}'."

            output = [f"### Web Search Results for: \"{query}\"\n"]
            for idx, r in enumerate(results, start=1):
                output.append(f"{idx}. **{r['title']}**")
                output.append(f"   - **URL:** {r['url']}")
                output.append(f"   - **Source:** {r['domain']}")
                output.append(f"   - **Snippet:** {r['snippet']}\n")

            return "\n".join(output).strip()

        except urllib.error.HTTPError as e:
            return f"Search HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return f"Search Network Failure: {e.reason}"
        except Exception as e:
            return f"Web search failed: {str(e)}"

    def _fetch(self, target_url: str) -> str:
        safe, reason = is_safe_url(target_url)
        if not safe:
            return f"Error: {reason}"

        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                content_type = resp.headers.get("Content-Type", "")
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()

                raw_bytes = resp.read(MAX_DOWNLOAD_BYTES)
                try:
                    html_content = raw_bytes.decode(charset, errors="replace")
                except Exception:
                    html_content = raw_bytes.decode("utf-8", errors="replace")

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
                f"**URL:** {target_url}",
                "---",
                "<untrusted_web_content>",
                extracted_text,
                "</untrusted_web_content>"
            ]

            if is_truncated:
                output.append("\n[Content truncated to stay within context limits]")

            return "\n".join(output)

        except urllib.error.HTTPError as e:
            return f"Fetch HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return f"Fetch Network Failure: {e.reason}"
        except TimeoutError:
            return f"Fetch Error: Connection timed out while reaching {target_url}."
        except Exception as e:
            return f"Error fetching webpage: {str(e)}"
