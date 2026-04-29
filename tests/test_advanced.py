"""
test_advanced.py
~~~~~~~~~~~~~~~~
Advanced API tests covering edge cases, regex filters, callable filters,
and iterators.
"""
import re
import pytest
from xhtml import Xhtml, Tag, NavigableString


HTML = """
<html>
<body>
  <article id="a1" class="post featured">
    <h2 class="post-title">First Post</h2>
    <p class="body-text">Hello <strong>world</strong>, this is a <em>test</em>.</p>
    <a href="https://external.com" rel="nofollow">Out</a>
    <a href="/internal">In</a>
  </article>
  <article id="a2" class="post">
    <h2 class="post-title">Second Post</h2>
    <p class="body-text">Another <strong>bold</strong> text.</p>
  </article>
  <aside>
    <ul>
      <li class="item" data-n="1">One</li>
      <li class="item" data-n="2">Two</li>
      <li class="item" data-n="3">Three</li>
    </ul>
  </aside>
</body>
</html>
"""


@pytest.fixture
def soup():
    return Xhtml(HTML, "html.parser")


# ─── Regex attribute filtering ────────────────────────────────────────────────

def test_regex_href(soup):
    links = soup.find_all("a", href=re.compile(r"^https?://"))
    assert len(links) == 1
    assert "external" in links[0]["href"]


def test_regex_class(soup):
    articles = soup.find_all("article", class_=re.compile("featured"))
    assert len(articles) == 1
    assert articles[0]["id"] == "a1"


def test_regex_id(soup):
    els = soup.find_all(id=re.compile(r"^a\d$"))
    assert len(els) == 2


# ─── Callable / lambda filters ────────────────────────────────────────────────

def test_lambda_find(soup):
    el = soup.find(lambda tag: tag.name == "article" and "featured" in tag.get("class", []))
    assert el is not None
    assert el["id"] == "a1"


def test_lambda_find_all(soup):
    items = soup.find_all(lambda tag: tag.name == "li" and tag.has_attr("data-n"))
    assert len(items) == 3


def test_lambda_no_match(soup):
    assert soup.find(lambda tag: tag.name == "video") is None


# ─── Multiple tag names ───────────────────────────────────────────────────────

def test_multi_tag_find_all(soup):
    els = soup.find_all(["h2", "strong"])
    names = [e.name for e in els]
    assert "h2" in names
    assert "strong" in names


def test_multi_tag_find(soup):
    el = soup.find(["h2", "h3"])
    assert el is not None
    assert el.name == "h2"


# ─── NavigableString ──────────────────────────────────────────────────────────

def test_navigable_string_is_str():
    s = Xhtml("<p>hello</p>", "html.parser")
    strings = list(s.find("p").strings)
    assert strings == ["hello"]


def test_stripped_strings_skips_whitespace():
    s = Xhtml("<p>  hello  </p>", "html.parser")
    stripped = list(s.find("p").stripped_strings)
    assert stripped == ["hello"]


# ─── Nested search isolation ──────────────────────────────────────────────────

def test_scoped_find_all(soup):
    """find_all inside a sub-element must not leak to siblings."""
    a1 = soup.find("article", id="a1")
    links = a1.find_all("a")
    assert len(links) == 2  # only links inside a1


def test_scoped_select(soup):
    a2 = soup.find("article", id="a2")
    titles = a2.select(".post-title")
    assert len(titles) == 1
    assert "Second" in titles[0].get_text()


# ─── Parent traversal ────────────────────────────────────────────────────────

def test_find_parent_by_name(soup):
    strong = soup.find("strong")
    article = strong.find_parent("article")
    assert article is not None


def test_find_parents_list(soup):
    li = soup.find("li")
    parents = li.find_parents()
    names = [p.name for p in parents]
    assert "ul" in names
    assert "aside" in names


# ─── Sibling navigation ───────────────────────────────────────────────────────

def test_next_sibling_element(soup):
    h2 = soup.find("h2")
    # Use find_next_sibling for reliable next-element traversal
    sib = h2.find_next_sibling("p")
    assert sib is not None
    assert sib.name == "p"


def test_previous_siblings_list(soup):
    last_li = soup.find_all("li")[-1]
    prev = list(last_li.previous_siblings)
    # Should have 2 previous siblings (the other two <li>s, possibly interleaved with text)
    li_sibs = [s for s in prev if hasattr(s, "name") and s.name == "li"]
    assert len(li_sibs) == 2


# ─── select() advanced ───────────────────────────────────────────────────────

def test_select_attribute_contains(soup):
    items = soup.select("li[data-n]")
    assert len(items) == 3


def test_select_nth_child(soup):
    items = soup.select("li:nth-child(2)")
    assert len(items) == 1
    assert items[0].get_text() == "Two"


def test_select_pseudo_first_child(soup):
    el = soup.select_one("li:first-child")
    assert el is not None
    assert el.get_text() == "One"


def test_select_descendant_of_scoped(soup):
    aside = soup.find("aside")
    items = aside.select("li.item")
    assert len(items) == 3


# ─── get_text() ──────────────────────────────────────────────────────────────

def test_get_text_full_document(soup):
    text = soup.get_text()
    assert "First Post" in text
    assert "Second Post" in text


def test_get_text_with_newline_separator():
    s = Xhtml("<div><p>foo</p><p>bar</p></div>", "html.parser")
    text = s.find("div").get_text("\n", strip=True)
    assert "foo" in text
    assert "bar" in text


# ─── Prettify ────────────────────────────────────────────────────────────────

def test_prettify_returns_string(soup):
    result = soup.find("h2").prettify()
    assert isinstance(result, str)
    assert "h2" in result


# ─── Iterator protocol ────────────────────────────────────────────────────────

def test_tag_iter(soup):
    ul = soup.find("ul")
    items = [c for c in ul if hasattr(c, "name") and c.name == "li"]
    assert len(items) == 3


def test_tag_len(soup):
    ul = soup.find("ul")
    assert len(ul) > 0


# ─── Encoding ────────────────────────────────────────────────────────────────

def test_encode_bytes(soup):
    h2 = soup.find("h2")
    assert isinstance(h2.encode("utf-8"), bytes)


def test_parse_latin1_bytes():
    b = "<p>caf\xe9</p>".encode("latin-1")
    s = Xhtml(b, "html.parser")
    # Should not crash; text extraction should work
    assert s.find("p") is not None


# ─── Equality and hashing ────────────────────────────────────────────────────

def test_tag_equality(soup):
    h2a = soup.find("h2")
    h2b = soup.find("h2")
    assert h2a == h2b


def test_tag_in_set(soup):
    h2 = soup.find("h2")
    tag_set = {h2}
    assert h2 in tag_set
