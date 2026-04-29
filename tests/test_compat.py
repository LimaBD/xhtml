"""
test_compat.py
~~~~~~~~~~~~~~
Compatibility tests ensuring xhtml behaves identically to beautifulsoup4.
These tests are designed to run against BOTH libraries — swap the import
line to verify.

Run against xhtml  : pytest tests/test_compat.py
Run against bs4 (ref) : BS4_MODE=1 pytest tests/test_compat.py
"""
import os
import pytest

if os.environ.get("BS4_MODE"):
    from bs4 import BeautifulSoup as Xhtml  # type: ignore[import]
else:
    from xhtml import Xhtml

from tests.conftest import (
    SIMPLE_HTML,
    NESTED_HTML,
    MULTI_CLASS_HTML,
    TABLE_HTML,
    SPECIAL_ATTRS_HTML,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def soup():
    return Xhtml(SIMPLE_HTML, "html.parser")


@pytest.fixture
def nested():
    return Xhtml(NESTED_HTML, "html.parser")


@pytest.fixture
def multi():
    return Xhtml(MULTI_CLASS_HTML, "html.parser")


@pytest.fixture
def tbl():
    return Xhtml(TABLE_HTML, "html.parser")


# ─── Parsing ─────────────────────────────────────────────────────────────────

def test_parse_html_string():
    s = Xhtml("<p>hello</p>", "html.parser")
    assert s.find("p") is not None


def test_parse_bytes():
    html_bytes = b"<p>hello bytes</p>"
    s = Xhtml(html_bytes, "html.parser")
    assert "hello bytes" in s.get_text()


def test_parse_unicode():
    s = Xhtml("<p>héllo wörld</p>", "html.parser")
    assert "héllo" in s.get_text()


def test_parse_empty():
    s = Xhtml("", "html.parser")
    assert s is not None


# ─── find() ──────────────────────────────────────────────────────────────────

def test_find_by_tag(soup):
    assert soup.find("h1").get_text() == "Hello World"


def test_find_by_class(soup):
    el = soup.find("h1", class_="title")
    assert el is not None
    assert el.get_text() == "Hello World"


def test_find_by_class_partial(soup):
    """class_='title' matches even when element has multiple classes."""
    el = soup.find("h1", class_="big")
    assert el is not None


def test_find_multi_class(soup):
    """class_='title big' (space-separated) requires BOTH classes."""
    el = soup.find(class_="title big")
    assert el is not None
    assert "Hello" in el.get_text()


def test_find_by_id(soup):
    el = soup.find(id="main")
    assert el is not None
    assert el.name == "div"


def test_find_returns_none(soup):
    assert soup.find("span") is None


def test_find_any_tag_with_class(soup):
    el = soup.find(class_="intro")
    assert el is not None
    assert el.name == "p"


def test_find_attr_true(soup):
    """find(href=True) matches any element that has an href attribute."""
    el = soup.find(href=True)
    assert el is not None
    assert el.name == "a"


def test_find_attr_value(soup):
    el = soup.find("a", href="/page2")
    assert el is not None
    assert "external" in el.get("class", [])


# ─── find_all() ──────────────────────────────────────────────────────────────

def test_find_all_by_tag(soup):
    links = soup.find_all("a")
    assert len(links) == 4


def test_find_all_by_class(soup):
    links = soup.find_all("a", class_="external")
    assert len(links) == 1
    assert links[0]["href"] == "/page2"


def test_find_all_with_limit(soup):
    links = soup.find_all("a", limit=2)
    assert len(links) == 2


def test_find_all_multi_tag(soup):
    els = soup.find_all(["h1", "p"])
    names = [el.name for el in els]
    assert "h1" in names
    assert "p" in names


def test_find_all_attr_exists(soup):
    links = soup.find_all("a", href=True)
    assert len(links) == 4


def test_find_all_nested(soup):
    """find_all on a sub-element must not include elements outside it."""
    div = soup.find("div", id="main")
    links = div.find_all("a")
    hrefs = [a["href"] for a in links]
    assert "/contact" not in hrefs
    assert len(links) == 3


def test_find_all_callable(soup):
    """find_all(lambda): callable name filter."""
    # SIMPLE_HTML has two links with class attrs: /page2 (external) and /contact (footer-link)
    tags = soup.find_all(lambda t: t.name == "a" and t.has_attr("class"))
    assert len(tags) == 2
    hrefs = [t["href"] for t in tags]
    assert "/page2" in hrefs
    assert "/contact" in hrefs


def test_find_all_returns_empty_list(soup):
    assert soup.find_all("video") == []


def test_find_all_multi_class(multi):
    els = multi.find_all(class_="foo bar")
    assert len(els) == 2  # <p class="foo bar baz"> and <p class="foo bar">


# ─── CSS select() / select_one() ─────────────────────────────────────────────

def test_select_tag(soup):
    items = soup.select("ul li a")
    assert len(items) == 3


def test_select_class(soup):
    els = soup.select(".external")
    assert len(els) == 1


def test_select_id(soup):
    els = soup.select("#main")
    assert len(els) == 1


def test_select_child_combinator(soup):
    els = soup.select("ul > li")
    assert len(els) == 3


def test_select_attribute(soup):
    els = soup.select("a[href='/page3']")
    assert len(els) == 1
    assert els[0].get("data-id") == "3"


def test_select_one_found(soup):
    el = soup.select_one("#main h1")
    assert el is not None
    assert el.get_text() == "Hello World"


def test_select_one_not_found(soup):
    assert soup.select_one(".does-not-exist") is None


def test_select_descendant(soup):
    els = soup.select("div#main p")
    assert len(els) == 2


# ─── Attribute access ────────────────────────────────────────────────────────

def test_getitem(soup):
    link = soup.find("a", class_="external")
    assert link["href"] == "/page2"


def test_getitem_keyerror(soup):
    link = soup.find("a")
    with pytest.raises(KeyError):
        _ = link["nonexistent"]


def test_get_attr(soup):
    link = soup.find("a")
    assert link.get("href") == "/page1"


def test_get_default(soup):
    link = soup.find("a")
    assert link.get("nonexistent", "default") == "default"


def test_has_attr_true(soup):
    link = soup.find("a", class_="external")
    assert link.has_attr("href")
    assert link.has_attr("class")


def test_has_attr_false(soup):
    link = soup.find("a")
    assert not link.has_attr("nonexistent")


def test_attrs_dict(soup):
    div = soup.find("div", id="main")
    attrs = div.attrs
    assert "container" in attrs.get("class", [])
    assert attrs.get("id") == "main"


def test_class_is_list(soup):
    h1 = soup.find("h1")
    cls = h1["class"]
    assert isinstance(cls, list)
    assert "title" in cls
    assert "big" in cls


# ─── Text extraction ─────────────────────────────────────────────────────────

def test_get_text_simple(soup):
    h1 = soup.find("h1")
    assert h1.get_text() == "Hello World"


def test_get_text_nested(soup):
    p = soup.find("p", class_="content")
    assert "bold" in p.get_text()


def test_get_text_separator(soup):
    ul = soup.find("ul")
    text = ul.get_text(" | ", strip=True)
    assert " | " in text


def test_get_text_strip(soup):
    h1 = soup.find("h1")
    assert h1.get_text(strip=True) == "Hello World"


def test_text_property(soup):
    h1 = soup.find("h1")
    assert h1.text == "Hello World"


def test_string_property(soup):
    h1 = soup.find("h1")
    assert h1.string == "Hello World"


def test_string_property_none_when_nested(soup):
    """string is None when there are multiple text nodes."""
    p = soup.find("p", class_="content")
    # <p class="content">Second <b>bold</b> paragraph</p> → multiple children
    assert p.string is None


def test_strings_generator(soup):
    p = soup.find("p", class_="content")
    strings = list(p.strings)
    assert any("bold" in s for s in strings)


def test_stripped_strings(soup):
    h1 = soup.find("h1")
    stripped = list(h1.stripped_strings)
    assert stripped == ["Hello World"]


# ─── Tree navigation ─────────────────────────────────────────────────────────

def test_parent(soup):
    h1 = soup.find("h1")
    assert h1.parent.name == "div"


def test_parent_chain(soup):
    h1 = soup.find("h1")
    assert h1.parent.parent.name == "body"


def test_children_contains_tags(soup):
    ul = soup.find("ul")
    tags = [c for c in ul.children if hasattr(c, "name")]
    li_names = [t.name for t in tags]
    assert all(n == "li" for n in li_names)
    assert len(li_names) == 3


def test_contents_list(soup):
    ul = soup.find("ul")
    contents = ul.contents
    assert any(hasattr(c, "name") and c.name == "li" for c in contents)


def test_descendants(soup):
    div = soup.find("div", id="main")
    all_desc = list(div.descendants)
    names = [d.name for d in all_desc if hasattr(d, "name")]
    assert "h1" in names
    assert "a" in names
    assert "li" in names


def test_next_sibling(soup):
    h1 = soup.find("h1")
    # Use find_next_sibling for reliable cross-parser element traversal
    sib = h1.find_next_sibling("p")
    assert sib is not None
    assert sib.name == "p"


def test_find_parent(soup):
    a = soup.find("a", href="/page1")
    li = a.find_parent("li")
    assert li is not None
    assert li.name == "li"


def test_find_parents(soup):
    a = soup.find("a", href="/page1")
    parents = a.find_parents()
    names = [p.name for p in parents]
    assert "li" in names
    assert "ul" in names


# ─── Rendering ───────────────────────────────────────────────────────────────

def test_str_renders_html(soup):
    h1 = soup.find("h1")
    html = str(h1)
    assert "<h1" in html
    assert "Hello World" in html


def test_repr_renders_html(soup):
    h1 = soup.find("h1")
    assert "h1" in repr(h1)


def test_encode(soup):
    h1 = soup.find("h1")
    encoded = h1.encode("utf-8")
    assert isinstance(encoded, bytes)
    assert b"Hello World" in encoded


# ─── Tables ──────────────────────────────────────────────────────────────────

def test_table_rows(tbl):
    rows = tbl.select("tbody tr")
    assert len(rows) == 2


def test_table_cells(tbl):
    cells = tbl.select("td")
    assert len(cells) == 4
    texts = [c.get_text() for c in cells]
    assert "Alice" in texts
    assert "Bob" in texts


# ─── Edge cases ──────────────────────────────────────────────────────────────

def test_fragment_parsing():
    s = Xhtml("<div><p>hello</p></div>", "html.parser")
    assert s.find("p").get_text() == "hello"


def test_deeply_nested():
    html = "<a><b><c><d><e>deep</e></d></c></b></a>"
    s = Xhtml(html, "html.parser")
    assert s.find("e").get_text() == "deep"


def test_malformed_html():
    """Parser must not crash on bad HTML."""
    s = Xhtml("<div><p>unclosed", "html.parser")
    assert s.find("div") is not None


def test_self_closing_tags():
    s = Xhtml('<img src="x.png"><br><input type="text">', "html.parser")
    assert s.find("img") is not None
    assert s.find("br") is not None


def test_multiple_parsers_all_accepted():
    """All parser names must be accepted (they all map to html5ever)."""
    for parser in ("html.parser", "lxml", "html5lib"):
        s = Xhtml("<p>ok</p>", parser)
        assert s.find("p") is not None


def test_title(soup):
    assert soup.find("title").string == "Test Page"


def test_find_by_data_attr():
    s = Xhtml('<a data-id="007">Link</a>', "html.parser")
    el = s.find(attrs={"data-id": "007"})
    assert el is not None
    assert el.name == "a"
