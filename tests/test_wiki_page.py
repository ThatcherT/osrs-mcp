"""Tests for wiki page reader (HTML parser + API integration)."""

import pytest
import httpx
import respx

from osrs_mcp.api.wiki_page import (
    html_to_text,
    fetch_page_sections,
    fetch_page_content,
    read_wiki_page,
    _resolve_section,
    WIKI_API,
    MAX_CHARS,
)


# ---------------------------------------------------------------------------
# HTML parser unit tests
# ---------------------------------------------------------------------------


class TestHTMLToText:
    def test_plain_paragraph(self):
        assert html_to_text("<p>Hello world</p>") == "Hello world"

    def test_heading_levels(self):
        html = '<h2><span id="Strategy">Strategy</span></h2>'
        text = html_to_text(html)
        assert "## Strategy" in text

    def test_heading_h3(self):
        html = '<h3><span id="Melee">Melee</span></h3>'
        text = html_to_text(html)
        assert "### Melee" in text

    def test_list_items(self):
        html = "<ul><li>First</li><li>Second</li></ul>"
        text = html_to_text(html)
        assert "- First" in text
        assert "- Second" in text

    def test_bold_preserved(self):
        html = "<p>Use a <b>dragon hunter lance</b> here.</p>"
        text = html_to_text(html)
        assert "**dragon hunter lance**" in text

    def test_strong_preserved(self):
        html = "<p><strong>Important</strong> note.</p>"
        text = html_to_text(html)
        assert "**Important**" in text

    def test_table_content(self):
        html = "<table><tr><th>Item</th><th>Qty</th></tr><tr><td>Bones</td><td>1</td></tr></table>"
        text = html_to_text(html)
        assert "Item" in text
        assert "Bones" in text

    def test_strips_edit_section(self):
        html = (
            '<h2>Strategy<span class="mw-editsection">'
            '[<a href="/edit">edit</a>]</span></h2>'
        )
        text = html_to_text(html)
        assert "edit" not in text.lower() or "edit" in "## Strategy"
        assert "## Strategy" in text

    def test_strips_navbox(self):
        html = '<div class="navbox">Nav content here</div><p>Real content</p>'
        text = html_to_text(html)
        assert "Nav content" not in text
        assert "Real content" in text

    def test_strips_infobox(self):
        html = '<table class="infobox">Infobox data</table><p>Paragraph</p>'
        text = html_to_text(html)
        assert "Infobox data" not in text
        assert "Paragraph" in text

    def test_strips_hatnote(self):
        html = '<div class="hatnote">For other uses, see X.</div><p>Main content</p>'
        text = html_to_text(html)
        assert "other uses" not in text
        assert "Main content" in text

    def test_strips_figure(self):
        html = '<div class="thumb"><div class="thumbinner">Image caption</div></div><p>Text</p>'
        text = html_to_text(html)
        assert "Image caption" not in text
        assert "Text" in text

    def test_strips_references(self):
        html = '<p>Content<sup class="reference">[1]</sup></p>'
        text = html_to_text(html)
        assert "[1]" not in text
        assert "Content" in text

    def test_entity_refs(self):
        html = "<p>A &amp; B &lt; C</p>"
        text = html_to_text(html)
        assert "A & B < C" in text

    def test_nbsp_entity(self):
        html = "<p>hello&nbsp;world</p>"
        text = html_to_text(html)
        assert "hello world" in text

    def test_whitespace_collapse(self):
        html = "<p>  lots   of   spaces  </p>"
        text = html_to_text(html)
        assert "lots of spaces" in text

    def test_br_becomes_newline(self):
        html = "<p>Line one<br>Line two</p>"
        text = html_to_text(html)
        assert "Line one" in text
        assert "Line two" in text

    def test_nested_skip(self):
        """If a parent is skipped, children should also be skipped."""
        html = '<div class="navbox"><p>Nested <b>bold</b> in navbox</p></div><p>Visible</p>'
        text = html_to_text(html)
        assert "Nested" not in text
        assert "bold" not in text
        assert "Visible" in text

    def test_empty_html(self):
        assert html_to_text("") == ""

    def test_script_stripped(self):
        html = "<script>var x = 1;</script><p>Safe</p>"
        text = html_to_text(html)
        assert "var x" not in text
        assert "Safe" in text


# ---------------------------------------------------------------------------
# Section resolution tests
# ---------------------------------------------------------------------------


class TestResolveSection:
    SECTIONS = [
        {"index": "1", "level": "2", "name": "Strategy"},
        {"index": "2", "level": "2", "name": "Drops"},
        {"index": "3", "level": "2", "name": "Unique drop table"},
        {"index": "4", "level": "3", "name": "Melee strategy"},
    ]

    SECTIONS_WITH_T = [
        {"index": "1", "level": "2", "name": "Drops"},
        {"index": "T-1", "level": "3", "name": "100%"},
        {"index": "T-2", "level": "3", "name": "Pre-roll"},
        {"index": "T-3", "level": "3", "name": "Weapons and armour"},
        {"index": "2", "level": "2", "name": "Strategy"},
    ]

    def test_exact_name(self):
        assert _resolve_section(self.SECTIONS, "Strategy") == "1"

    def test_case_insensitive(self):
        assert _resolve_section(self.SECTIONS, "strategy") == "1"

    def test_substring_match(self):
        assert _resolve_section(self.SECTIONS, "Unique drop") == "3"

    def test_by_index(self):
        assert _resolve_section(self.SECTIONS, "2") == "2"

    def test_not_found(self):
        assert _resolve_section(self.SECTIONS, "Nonexistent") is None

    def test_invalid_index(self):
        assert _resolve_section(self.SECTIONS, "99") is None

    def test_t_index_by_name(self):
        assert _resolve_section(self.SECTIONS_WITH_T, "Pre-roll") == "T-2"

    def test_t_index_substring(self):
        assert _resolve_section(self.SECTIONS_WITH_T, "Weapons") == "T-3"


# ---------------------------------------------------------------------------
# API integration tests (respx-mocked)
# ---------------------------------------------------------------------------

MOCK_SECTIONS_RESPONSE = {
    "parse": {
        "title": "Vorkath",
        "sections": [
            {"index": "1", "level": "2", "line": "Strategy"},
            {"index": "2", "level": "2", "line": "Drops"},
            {"index": "3", "level": "3", "line": "Unique drop table"},
        ],
    }
}

MOCK_INTRO_HTML_RESPONSE = {
    "parse": {
        "title": "Vorkath",
        "text": "<p>Vorkath is a boss encountered during Dragon Slayer II.</p>",
    }
}

MOCK_SECTION_HTML_RESPONSE = {
    "parse": {
        "title": "Vorkath",
        "text": '<h2>Strategy</h2><p>Use <b>ranged</b> with a dragon hunter crossbow.</p>',
    }
}

MOCK_ERROR_RESPONSE = {
    "error": {
        "code": "missingtitle",
        "info": 'The page "Nonexistent" does not exist.',
    }
}


class TestFetchPageSections:
    @respx.mock
    @pytest.mark.anyio
    async def test_returns_sections(self):
        respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_SECTIONS_RESPONSE)
        )
        sections = await fetch_page_sections("Vorkath")
        assert len(sections) == 3
        assert sections[0]["name"] == "Strategy"
        assert sections[0]["index"] == "1"
        assert sections[2]["name"] == "Unique drop table"

    @respx.mock
    @pytest.mark.anyio
    async def test_missing_page(self):
        respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_ERROR_RESPONSE)
        )
        sections = await fetch_page_sections("Nonexistent Page")
        assert sections == []

    @respx.mock
    @pytest.mark.anyio
    async def test_caching(self):
        route = respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_SECTIONS_RESPONSE)
        )
        await fetch_page_sections("Vorkath")
        await fetch_page_sections("Vorkath")
        assert route.call_count == 1


class TestFetchPageContent:
    @respx.mock
    @pytest.mark.anyio
    async def test_returns_text(self):
        respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_INTRO_HTML_RESPONSE)
        )
        text = await fetch_page_content("Vorkath", section=0)
        assert "Vorkath is a boss" in text

    @respx.mock
    @pytest.mark.anyio
    async def test_missing_page_returns_empty(self):
        respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_ERROR_RESPONSE)
        )
        text = await fetch_page_content("Nonexistent")
        assert text == ""


class TestReadWikiPage:
    @respx.mock
    @pytest.mark.anyio
    async def test_no_section_returns_toc_and_intro(self):
        respx.get(WIKI_API).mock(side_effect=_mock_vorkath_dispatcher)
        result = await read_wiki_page("Vorkath")
        assert result["page"] == "Vorkath"
        assert "oldschool.runescape.wiki" in result["url"]
        assert "sections" in result
        assert len(result["sections"]) == 3
        assert "Vorkath is a boss" in result["intro"]

    @respx.mock
    @pytest.mark.anyio
    async def test_section_by_name(self):
        respx.get(WIKI_API).mock(side_effect=_mock_vorkath_dispatcher)
        result = await read_wiki_page("Vorkath", section="Strategy")
        assert "content" in result
        assert "ranged" in result["content"]

    @respx.mock
    @pytest.mark.anyio
    async def test_section_not_found(self):
        respx.get(WIKI_API).mock(side_effect=_mock_vorkath_dispatcher)
        result = await read_wiki_page("Vorkath", section="Nonexistent")
        assert "error" in result
        assert "not found" in result["error"]
        assert "available_sections" in result

    @respx.mock
    @pytest.mark.anyio
    async def test_page_not_found(self):
        respx.get(WIKI_API).mock(
            return_value=httpx.Response(200, json=MOCK_ERROR_RESPONSE)
        )
        result = await read_wiki_page("Totally Fake Page")
        assert "error" in result
        assert "not found" in result["error"]

    @respx.mock
    @pytest.mark.anyio
    async def test_truncation(self):
        long_text = "A" * (MAX_CHARS + 500)
        long_response = {
            "parse": {"title": "Long", "text": f"<p>{long_text}</p>"}
        }
        respx.get(WIKI_API).mock(side_effect=_make_dispatcher(
            sections_resp=MOCK_SECTIONS_RESPONSE,
            intro_resp=long_response,
            section_resp=long_response,
        ))
        result = await read_wiki_page("Long")
        assert "[Truncated" in result["intro"]
        assert len(result["intro"]) < MAX_CHARS + 200


# ---------------------------------------------------------------------------
# Mock dispatchers
# ---------------------------------------------------------------------------


def _mock_vorkath_dispatcher(request: httpx.Request) -> httpx.Response:
    """Route mock responses based on query params."""
    params = dict(request.url.params)
    prop = params.get("prop", "")
    section = params.get("section")

    if prop == "sections":
        return httpx.Response(200, json=MOCK_SECTIONS_RESPONSE)
    elif prop == "text" and section == "0":
        return httpx.Response(200, json=MOCK_INTRO_HTML_RESPONSE)
    elif prop == "text" and section is not None:
        return httpx.Response(200, json=MOCK_SECTION_HTML_RESPONSE)
    elif prop == "text":
        return httpx.Response(200, json=MOCK_INTRO_HTML_RESPONSE)
    return httpx.Response(200, json=MOCK_ERROR_RESPONSE)


def _make_dispatcher(sections_resp, intro_resp, section_resp):
    """Create a dispatcher with custom responses."""
    def dispatch(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        prop = params.get("prop", "")
        section = params.get("section")

        if prop == "sections":
            return httpx.Response(200, json=sections_resp)
        elif prop == "text" and section == "0":
            return httpx.Response(200, json=intro_resp)
        elif prop == "text" and section is not None:
            return httpx.Response(200, json=section_resp)
        elif prop == "text":
            return httpx.Response(200, json=intro_resp)
        return httpx.Response(200, json=MOCK_ERROR_RESPONSE)
    return dispatch
