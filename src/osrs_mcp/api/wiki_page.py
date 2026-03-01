"""Fetch and parse OSRS Wiki page content via the MediaWiki API."""

from __future__ import annotations

from html.parser import HTMLParser

from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache

WIKI_API = "https://oldschool.runescape.wiki/api.php"
MAX_CHARS = 4000
CACHE_TTL = 600  # 10 minutes

# ---------------------------------------------------------------------------
# HTML → plain-text converter
# ---------------------------------------------------------------------------

_STRIP_CLASSES = frozenset({
    "navbox", "mw-editsection", "infobox", "hatnote", "dablink",
    "thumb", "tright", "tleft", "floatright", "floatleft",
    "reference", "mw-references-wrap", "reflist",
    "mw-empty-elt",
})

_STRIP_TAGS = frozenset({"script", "style"})

_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

_BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "tr", "table", "blockquote", "pre",
    "dl", "dt", "dd", "section", "article", "aside", "header", "footer",
})


class _WikiHTMLToText(HTMLParser):
    """Stack-based HTML→text converter that strips wiki chrome."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_stack: list[bool] = []

    @property
    def _skipping(self) -> bool:
        return any(self._skip_stack)

    # -- tag handling -------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        classes = set((attr_dict.get("class") or "").split())

        skip = (
            tag in _STRIP_TAGS
            or bool(classes & _STRIP_CLASSES)
            or attr_dict.get("role") == "navigation"
        )

        if tag in _VOID_TAGS:
            # Void tags never get a matching endtag — handle inline.
            if not self._skipping and not skip:
                if tag == "br":
                    self._parts.append("\n")
            return

        self._skip_stack.append(skip)

        if self._skipping:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._parts.append("\n" + "#" * level + " ")
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag == "b" or tag == "strong":
            self._parts.append("**")
        elif tag == "th":
            self._parts.append("**")
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return

        was_skipping = self._skipping
        if self._skip_stack:
            self._skip_stack.pop()

        if was_skipping:
            return

        if tag == "b" or tag == "strong":
            self._parts.append("**")
        elif tag == "th":
            self._parts.append("** | ")
        elif tag == "td":
            self._parts.append(" | ")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")
        elif tag in ("p", "tr"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        entity_map = {"amp": "&", "lt": "<", "gt": ">", "nbsp": " ", "quot": '"'}
        if not self._skipping:
            self._parts.append(entity_map.get(name, f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if not self._skipping:
            try:
                if name.startswith("x"):
                    char = chr(int(name[1:], 16))
                else:
                    char = chr(int(name))
                self._parts.append(char)
            except (ValueError, OverflowError):
                self._parts.append(f"&#{name};")

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of whitespace (preserving newlines)
        lines = raw.split("\n")
        cleaned = []
        for line in lines:
            collapsed = " ".join(line.split())
            cleaned.append(collapsed)
        text = "\n".join(cleaned)
        # Collapse 3+ consecutive newlines to 2
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip()


def html_to_text(html: str) -> str:
    """Convert MediaWiki HTML to clean plain text."""
    parser = _WikiHTMLToText()
    parser.feed(html)
    return parser.get_text()


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------


async def fetch_page_sections(page: str) -> list[dict]:
    """Get the table of contents for a wiki page.

    Returns list of {"index": "1", "level": "2", "name": "Strategy"} dicts.
    """
    cache_key = f"wiki_sections:{page}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    resp = await client.get(WIKI_API, params={
        "action": "parse",
        "page": page,
        "prop": "sections",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    })
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        return []

    sections = [
        {
            "index": s["index"],
            "level": s.get("level", "2"),
            "name": s.get("line", ""),
        }
        for s in data.get("parse", {}).get("sections", [])
    ]
    cache.set(cache_key, sections, ttl=CACHE_TTL)
    return sections


async def fetch_page_content(page: str, section: int | None = None) -> str:
    """Fetch HTML for a page (or one section) and convert to text.

    Args:
        page: Wiki page title.
        section: Section index (0 = intro only). None = full page.
    """
    cache_key = f"wiki_content:{page}:{section}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params: dict = {
        "action": "parse",
        "page": page,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    }
    if section is not None:
        params["section"] = section

    client = get_client()
    resp = await client.get(WIKI_API, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        return ""

    html = data.get("parse", {}).get("text", "")
    text = html_to_text(html)
    cache.set(cache_key, text, ttl=CACHE_TTL)
    return text


def _resolve_section(sections: list[dict], section: str) -> int | None:
    """Resolve a section name or index string to a numeric section index.

    Tries exact match, then case-insensitive, then substring.
    Also accepts a raw integer string like "3".
    """
    # Raw index
    if section.isdigit():
        idx = int(section)
        if any(s["index"] == str(idx) for s in sections):
            return idx
        return None

    name = section.strip()

    # Exact match
    for s in sections:
        if s["name"] == name:
            return int(s["index"])

    # Case-insensitive match
    lower = name.lower()
    for s in sections:
        if s["name"].lower() == lower:
            return int(s["index"])

    # Substring / fuzzy match
    for s in sections:
        if lower in s["name"].lower():
            return int(s["index"])

    return None


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


async def read_wiki_page(page: str, section: str = "") -> dict:
    """Read an OSRS Wiki page or a specific section of it.

    Args:
        page: Page title (e.g. "Vorkath", "Dragon Slayer I").
        section: Optional section name or index. Leave empty for the
                 table of contents + intro.

    Returns:
        Dict with page, url, and content (or toc + intro).
    """
    url = f"https://oldschool.runescape.wiki/w/{page.replace(' ', '_')}"

    if not section:
        # Return TOC + intro
        sections = await fetch_page_sections(page)
        intro = await fetch_page_content(page, section=0)

        if not sections and not intro:
            return {
                "page": page,
                "url": url,
                "error": f"Page '{page}' not found. Try search_wiki() to find the correct title.",
            }

        toc = [f"{s['index']}. {s['name']}" for s in sections]

        result_text = intro
        if len(result_text) > MAX_CHARS:
            result_text = result_text[:MAX_CHARS] + "\n\n[Truncated — request a specific section for more]"

        return {
            "page": page,
            "url": url,
            "sections": toc,
            "intro": result_text,
        }

    # Resolve section name → index
    sections = await fetch_page_sections(page)
    if not sections:
        return {
            "page": page,
            "url": url,
            "error": f"Page '{page}' not found. Try search_wiki() to find the correct title.",
        }

    section_idx = _resolve_section(sections, section)
    if section_idx is None:
        toc = [f"{s['index']}. {s['name']}" for s in sections]
        return {
            "page": page,
            "url": url,
            "error": f"Section '{section}' not found.",
            "available_sections": toc,
        }

    content = await fetch_page_content(page, section=section_idx)

    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n\n[Truncated — section too long]"

    return {
        "page": page,
        "url": url,
        "section": section,
        "content": content,
    }
