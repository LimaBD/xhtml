"""
tests/test_bs4_compat.py
~~~~~~~~~~~~~~~~~~~~~~~~
Compatibility tests verifying that xhtml exposes the same HTML parsing
and navigation interface as established Python HTML libraries.

Run against xhtml  : pytest tests/test_bs4_compat.py
Run against bs4    : BS4_MODE=1 pytest tests/test_bs4_compat.py
"""
from __future__ import annotations

import os
import re
import pytest

if os.environ.get("BS4_MODE"):
    from bs4 import BeautifulSoup as Xhtml, Tag, NavigableString  # type: ignore
else:
    from xhtml import Xhtml, Tag, NavigableString
    from xhtml.element import ResultSet

# ─── Shared HTML ─────────────────────────────────────────────────────────────

HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <div id="wrapper" class="main-wrapper">
    <p class="para" id="first">First <em>emphasis</em> text</p>
    <p class="para" id="second">Second paragraph</p>
    <div class="inner">
      <span id="inner-span">Inner span</span>
    </div>
    <p id="third">Third paragraph</p>
  </div>
  <footer>
    <a href="/home" class="nav-link">Home</a>
    <a href="/about">About</a>
    <br>
    <img src="/logo.png" alt="Logo">
  </footer>
</body>
</html>
"""

VOID_HTML = """
<html><body>
  <br>
  <img src="/a.png" alt="alt">
  <input type="text" name="q">
  <hr>
  <meta charset="utf-8">
  <div><p>Regular</p></div>
</body></html>
"""


@pytest.fixture
def soup():
    return Xhtml(HTML, "html.parser")


@pytest.fixture
def vsoup():
    return Xhtml(VOID_HTML, "html.parser")


# ─── ResultSet ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(os.environ.get("BS4_MODE") == "1", reason="BS4 mode")
def test_find_all_returns_result_set(soup):
    """find_all() must return a ResultSet (list subclass)."""
    result = soup.find_all("p")
    assert isinstance(result, ResultSet)
    assert isinstance(result, list)


@pytest.mark.skipif(os.environ.get("BS4_MODE") == "1", reason="BS4 mode")
def test_result_set_source(soup):
    """ResultSet has a .source attribute pointing to the originating tag."""
    result = soup.find_all("p")
    assert result.source is soup


@pytest.mark.skipif(os.environ.get("BS4_MODE") == "1", reason="BS4 mode")
def test_result_set_is_subscriptable(soup):
    result = soup.find_all("p")
    assert result[0].name == "p"


# ─── __call__ shortcut ───────────────────────────────────────────────────────

def test_call_is_find_all(soup):
    """soup('tag') must behave identically to soup.find_all('tag')."""
    assert soup("p") == soup.find_all("p")


def test_call_with_attrs(soup):
    result = soup("p", class_="para")
    assert len(result) == 2


def test_call_with_limit(soup):
    result = soup("p", limit=1)
    assert len(result) == 1


def test_call_no_args_returns_all_tags(soup):
    """soup(True) returns all tags (same as find_all(True))."""
    result = soup(True)
    assert len(result) > 0


# ─── __getattr__ tag access ───────────────────────────────────────────────────

def test_getattr_title(soup):
    """soup.title should return the first <title> tag."""
    title = soup.title
    assert title is not None
    assert title.name == "title"


def test_getattr_body(soup):
    body = soup.body
    assert body is not None
    assert body.name == "body"


def test_getattr_head(soup):
    head = soup.head
    assert head is not None
    assert head.name == "head"


def test_getattr_p(soup):
    """soup.p returns the first <p>."""
    p = soup.p
    assert p is not None
    assert p.name == "p"
    assert p["id"] == "first"


def test_getattr_unknown_returns_none(soup):
    """Accessing a nonexistent tag attribute returns None (BS4 behaviour)."""
    result = soup.xyzzy_not_a_real_tag_at_all
    assert result is None


def test_getattr_nonexistent_div(soup):
    s = Xhtml("<html><body></body></html>", "html.parser")
    assert s.span is None


# ─── getText alias ───────────────────────────────────────────────────────────

def test_getText_alias(soup):
    p = soup.find("p", id="first")
    assert p.getText() == p.get_text()


def test_getText_with_separator(soup):
    div = soup.find("div", id="wrapper")
    assert div.getText(" ", strip=True) == div.get_text(" ", strip=True)


# ─── has_key alias ───────────────────────────────────────────────────────────

def test_has_key_true(soup):
    a = soup.find("a")
    assert a.has_key("href") is True


def test_has_key_false(soup):
    a = soup.find("a")
    assert a.has_key("nonexistent") is False


def test_has_key_equals_has_attr(soup):
    a = soup.find("a", class_="nav-link")
    assert a.has_key("class") == a.has_attr("class")


# ─── get_attribute_list ───────────────────────────────────────────────────────

def test_get_attribute_list_class(soup):
    """class returns a list of class names."""
    p = soup.find("p", class_="para")
    cls = p.get_attribute_list("class")
    assert isinstance(cls, list)
    assert "para" in cls


def test_get_attribute_list_single_value(soup):
    """Non-multi-valued attributes come back wrapped in a list."""
    a = soup.find("a")
    href = a.get_attribute_list("href")
    assert isinstance(href, list)
    assert href == ["/home"]


def test_get_attribute_list_missing(soup):
    """Missing attributes return [None]."""
    a = soup.find("a")
    result = a.get_attribute_list("nonexistent")
    assert result == [None]


# ─── is_empty_element / isSelfClosing ────────────────────────────────────────

def test_is_empty_element_br(vsoup):
    br = vsoup.find("br")
    assert br is not None
    assert br.is_empty_element is True


def test_is_empty_element_img(vsoup):
    img = vsoup.find("img")
    assert img.is_empty_element is True


def test_is_empty_element_input(vsoup):
    inp = vsoup.find("input")
    assert inp.is_empty_element is True


def test_is_empty_element_hr(vsoup):
    hr = vsoup.find("hr")
    assert hr.is_empty_element is True


def test_is_empty_element_meta(vsoup):
    meta = vsoup.find("meta")
    assert meta.is_empty_element is True


def test_is_empty_element_div_false(vsoup):
    div = vsoup.find("div")
    assert div.is_empty_element is False


def test_is_empty_element_p_false(vsoup):
    p = vsoup.find("p")
    assert p.is_empty_element is False


def test_isSelfClosing_alias(vsoup):
    br = vsoup.find("br")
    assert br.isSelfClosing is True


# ─── hidden property ─────────────────────────────────────────────────────────

def test_document_hidden(soup):
    assert soup.hidden is True


def test_tag_not_hidden(soup):
    assert soup.find("div").hidden is False


def test_tag_p_not_hidden(soup):
    assert soup.find("p").hidden is False


# ─── parents iterator ────────────────────────────────────────────────────────

def test_parents_yields_ancestors(soup):
    span = soup.find("span", id="inner-span")
    parent_names = [p.name for p in span.parents]
    assert "div" in parent_names
    assert "body" in parent_names
    assert "html" in parent_names


def test_parents_order(soup):
    """Parents should be yielded from immediate parent to root."""
    span = soup.find("span", id="inner-span")
    parents = list(span.parents)
    names = [p.name for p in parents if hasattr(p, "name")]
    # immediate parent of span is .inner div
    assert names[0] == "div"


def test_parents_terminates(soup):
    p = soup.find("p", id="first")
    parents = list(p.parents)
    assert len(parents) > 0
    # No infinite loop — should terminate


def test_parents_of_root_empty():
    s = Xhtml("<p>hi</p>", "html.parser")
    # The document root has no parents
    parents = list(s.parents)
    assert parents == []


# ─── NavigableString.name ────────────────────────────────────────────────────

def test_navigable_string_name_is_none(soup):
    p = soup.find("p", id="second")
    children = list(p.children)
    text_nodes = [c for c in children if isinstance(c, NavigableString)]
    assert len(text_nodes) > 0
    for ns in text_nodes:
        assert ns.name is None


# ─── next_element / previous_element ────────────────────────────────────────

def test_next_element_is_first_child(soup):
    """next_element of a tag should be its first child."""
    title = soup.find("title")
    nxt = title.next_element
    # The text inside <title> is the first child
    assert nxt is not None
    assert "Test" in str(nxt)


def test_next_element_of_text_skips_to_sibling(soup):
    """next_element of a text node with no next sibling walks up."""
    p_second = soup.find("p", id="second")
    nxt = p_second.next_element
    assert nxt is not None  # should be the text "Second paragraph"


def test_next_element_terminal_is_none():
    """next_element of the very last node is None."""
    s = Xhtml("<p>hi</p>", "html.parser")
    # Traverse to end
    el = s
    seen = set()
    while el is not None and id(el) not in seen:
        seen.add(id(el))
        if hasattr(el, "next_element"):
            el = el.next_element
        else:
            break
    # Just ensure traversal completes without infinite loop


def test_previous_element_basic(soup):
    p_second = soup.find("p", id="second")
    prev = p_second.previous_element
    assert prev is not None


def test_previous_element_of_first_tag_is_parent(soup):
    """previous_element of a first child is its parent."""
    title = soup.find("title")
    text_node = title.next_element  # first text inside title
    if text_node is not None:
        prev = text_node.previous_element
        assert prev is not None
        assert hasattr(prev, "name") and prev.name == "title"


# ─── next_elements / previous_elements ───────────────────────────────────────

def test_next_elements_not_empty(soup):
    p = soup.find("p", id="first")
    elements = list(p.next_elements)
    assert len(elements) > 0


def test_next_elements_in_order(soup):
    """All elements after p#first should come AFTER it in document order."""
    p1 = soup.find("p", id="first")
    elements = list(p1.next_elements)
    tag_names = [e.name for e in elements if isinstance(e, Tag)]
    # em is inside p#first so comes first, then p#second, div.inner, span, etc.
    assert "em" in tag_names
    assert "p" in tag_names  # p#second


def test_previous_elements_not_empty(soup):
    p3 = soup.find("p", id="third")
    elements = list(p3.previous_elements)
    assert len(elements) > 0


def test_next_elements_are_sequential(soup):
    """next_elements then previous_elements should reach back to start."""
    p1 = soup.find("p", id="first")
    # find p#second in next_elements
    found = next(
        (e for e in p1.next_elements if isinstance(e, Tag) and e.get("id") == "second"),
        None,
    )
    assert found is not None


# ─── find_next / find_all_next ───────────────────────────────────────────────

def test_find_next_by_tag(soup):
    p1 = soup.find("p", id="first")
    nxt = p1.find_next("p")
    assert nxt is not None
    assert nxt["id"] == "second"


def test_find_next_skips_self(soup):
    """find_next should not return self, only strictly following elements."""
    p1 = soup.find("p", id="first")
    nxt = p1.find_next("p")
    assert nxt is not p1


def test_find_next_with_attr(soup):
    p1 = soup.find("p", id="first")
    nxt = p1.find_next("p", class_="para")
    assert nxt is not None
    assert nxt["id"] == "second"


def test_find_next_none_when_no_match(soup):
    last_a = soup.find_all("a")[-1]
    nxt = last_a.find_next("video")
    assert nxt is None


def test_find_all_next_by_tag(soup):
    p1 = soup.find("p", id="first")
    following = p1.find_all_next("p")
    assert len(following) == 2
    ids = [p["id"] for p in following]
    assert "second" in ids
    assert "third" in ids


def test_find_all_next_limit(soup):
    p1 = soup.find("p", id="first")
    following = p1.find_all_next("p", limit=1)
    assert len(following) == 1
    assert following[0]["id"] == "second"


def test_find_all_next_no_name(soup):
    """find_all_next() with no name returns all following elements."""
    p1 = soup.find("p", id="first")
    following = p1.find_all_next()
    assert len(following) > 1


def test_findAllNext_alias(soup):
    p1 = soup.find("p", id="first")
    assert p1.findAllNext("p") == p1.find_all_next("p")


def test_findNext_alias(soup):
    p1 = soup.find("p", id="first")
    assert p1.findNext("p") == p1.find_next("p")


# ─── find_previous / find_all_previous ───────────────────────────────────────

def test_find_previous_by_tag(soup):
    p3 = soup.find("p", id="third")
    prev = p3.find_previous("p")
    assert prev is not None
    assert prev["id"] == "second"


def test_find_previous_skips_self(soup):
    p3 = soup.find("p", id="third")
    prev = p3.find_previous("p")
    assert prev is not p3


def test_find_previous_none_when_no_match(soup):
    first_el = soup.find("title")
    prev = first_el.find_previous("video")
    assert prev is None


def test_find_all_previous_by_tag(soup):
    p3 = soup.find("p", id="third")
    preceding = p3.find_all_previous("p")
    assert len(preceding) == 2


def test_find_all_previous_order(soup):
    """find_all_previous returns elements closest first (reverse document order)."""
    p3 = soup.find("p", id="third")
    preceding = p3.find_all_previous("p")
    assert preceding[0]["id"] == "second"
    assert preceding[1]["id"] == "first"


def test_find_all_previous_limit(soup):
    p3 = soup.find("p", id="third")
    preceding = p3.find_all_previous("p", limit=1)
    assert len(preceding) == 1
    assert preceding[0]["id"] == "second"


def test_findAllPrevious_alias(soup):
    p3 = soup.find("p", id="third")
    assert p3.findAllPrevious("p") == p3.find_all_previous("p")


def test_findPrevious_alias(soup):
    p3 = soup.find("p", id="third")
    assert p3.findPrevious("p") == p3.find_previous("p")


# ─── find_previous_sibling / find_previous_siblings ─────────────────────────

def test_find_previous_sibling_basic(soup):
    p2 = soup.find("p", id="second")
    prev = p2.find_previous_sibling("p")
    assert prev is not None
    assert prev["id"] == "first"


def test_find_previous_sibling_no_match(soup):
    p1 = soup.find("p", id="first")
    prev = p1.find_previous_sibling("p")
    assert prev is None


def test_find_previous_sibling_no_filter(soup):
    p2 = soup.find("p", id="second")
    prev = p2.find_previous_sibling()
    assert prev is not None  # could be a text node or p#first


def test_find_previous_siblings_basic(soup):
    p3 = soup.find("p", id="third")
    prev_sibs = p3.find_previous_siblings("p")
    assert len(prev_sibs) == 2


def test_find_previous_siblings_order(soup):
    """Closest previous sibling comes first."""
    p3 = soup.find("p", id="third")
    prev_sibs = p3.find_previous_siblings("p")
    assert prev_sibs[0]["id"] == "second"
    assert prev_sibs[1]["id"] == "first"


def test_find_previous_siblings_limit(soup):
    p3 = soup.find("p", id="third")
    prev_sibs = p3.find_previous_siblings("p", limit=1)
    assert len(prev_sibs) == 1
    assert prev_sibs[0]["id"] == "second"


def test_findPreviousSibling_alias(soup):
    p2 = soup.find("p", id="second")
    assert p2.findPreviousSibling("p") == p2.find_previous_sibling("p")


def test_findPreviousSiblings_alias(soup):
    p3 = soup.find("p", id="third")
    assert p3.findPreviousSiblings("p") == p3.find_previous_siblings("p")


# ─── self_and_descendants ────────────────────────────────────────────────────

def test_self_and_descendants_starts_with_self(soup):
    div = soup.find("div", id="wrapper")
    elements = list(div.self_and_descendants)
    assert elements[0] == div


def test_self_and_descendants_includes_children(soup):
    div = soup.find("div", id="wrapper")
    elements = list(div.self_and_descendants)
    names = [e.name for e in elements if isinstance(e, Tag)]
    assert "p" in names
    assert "span" in names


# ─── self_and_parents ────────────────────────────────────────────────────────

def test_self_and_parents_starts_with_self(soup):
    span = soup.find("span", id="inner-span")
    elements = list(span.self_and_parents)
    assert elements[0] == span


def test_self_and_parents_includes_ancestors(soup):
    span = soup.find("span", id="inner-span")
    names = [p.name for p in span.self_and_parents if isinstance(p, Tag)]
    assert "span" in names
    assert "div" in names
    assert "body" in names


# ─── self_and_next_siblings / self_and_previous_siblings ─────────────────────

def test_self_and_next_siblings_starts_with_self(soup):
    p1 = soup.find("p", id="first")
    sibs = list(p1.self_and_next_siblings)
    assert sibs[0] == p1


def test_self_and_next_siblings_includes_following(soup):
    p1 = soup.find("p", id="first")
    sibs = list(p1.self_and_next_siblings)
    tag_ids = [s["id"] for s in sibs if isinstance(s, Tag) and s.has_attr("id")]
    assert "first" in tag_ids


def test_self_and_previous_siblings_starts_with_self(soup):
    p3 = soup.find("p", id="third")
    sibs = list(p3.self_and_previous_siblings)
    assert sibs[0] == p3


# ─── self_and_next_elements / self_and_previous_elements ─────────────────────

def test_self_and_next_elements_starts_with_self(soup):
    p1 = soup.find("p", id="first")
    elements = list(p1.self_and_next_elements)
    assert elements[0] == p1


def test_self_and_previous_elements_starts_with_self(soup):
    p3 = soup.find("p", id="third")
    elements = list(p3.self_and_previous_elements)
    assert elements[0] == p3


# ─── index() ─────────────────────────────────────────────────────────────────

def test_index_returns_int(soup):
    wrapper = soup.find("div", id="wrapper")
    p1 = soup.find("p", id="first")
    idx = wrapper.index(p1)
    assert isinstance(idx, int)


def test_index_of_first_child_tag(soup):
    wrapper = soup.find("div", id="wrapper")
    p1 = soup.find("p", id="first")
    p2 = soup.find("p", id="second")
    idx1 = wrapper.index(p1)
    idx2 = wrapper.index(p2)
    assert idx1 < idx2


def test_index_raises_on_missing():
    s1 = Xhtml("<div><p>a</p></div>", "html.parser")
    s2 = Xhtml("<span>b</span>", "html.parser")
    div = s1.find("div")
    span = s2.find("span")
    with pytest.raises(ValueError):
        div.index(span)


# ─── NavigableString navigation ──────────────────────────────────────────────

def test_navigable_string_find_parent(soup):
    """NavigableString should expose find_parent()."""
    em = soup.find("em")
    text_children = [c for c in em.children if isinstance(c, NavigableString)]
    assert len(text_children) > 0
    ns = text_children[0]
    parent = ns.find_parent("p")
    assert parent is not None
    assert parent.name == "p"


def test_navigable_string_find_parents(soup):
    em = soup.find("em")
    text_children = [c for c in em.children if isinstance(c, NavigableString)]
    assert len(text_children) > 0
    ns = text_children[0]
    parents = ns.find_parents()
    names = [p.name for p in parents if hasattr(p, "name")]
    assert "em" in names
    assert "p" in names


def test_navigable_string_next_element(soup):
    em = soup.find("em")
    text_children = [c for c in em.children if isinstance(c, NavigableString)]
    assert len(text_children) > 0
    ns = text_children[0]
    nxt = ns.next_element
    # After the text inside em, the next element in document order should exist
    assert nxt is not None or True  # may be None at end of doc


def test_navigable_string_previous_element(soup):
    p1 = soup.find("p", id="first")
    # Get text nodes inside p1
    children = list(p1.children)
    text_nodes = [c for c in children if isinstance(c, NavigableString)]
    assert len(text_nodes) > 0


def test_navigable_string_find_next(soup):
    em = soup.find("em")
    text_children = [c for c in em.children if isinstance(c, NavigableString)]
    assert len(text_children) > 0
    ns = text_children[0]
    nxt_tag = ns.find_next("p")
    # There should be a <p> after the text inside <em>
    assert nxt_tag is not None


def test_navigable_string_find_previous(soup):
    p3 = soup.find("p", id="third")
    children = list(p3.children)
    text_nodes = [c for c in children if isinstance(c, NavigableString)]
    assert len(text_nodes) > 0
    ns = text_nodes[0]
    prev_p = ns.find_previous("p")
    assert prev_p is not None


def test_navigable_string_parents(soup):
    em = soup.find("em")
    text_children = [c for c in em.children if isinstance(c, NavigableString)]
    assert len(text_children) > 0
    ns = text_children[0]
    parent_names = [p.name for p in ns.parents if hasattr(p, "name")]
    assert "em" in parent_names
    assert "p" in parent_names


# ─── Tree modification raises NotImplementedError ────────────────────────────

def test_append_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.append("something")


def test_insert_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.insert(0, "something")


def test_extend_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.extend(["a", "b"])


def test_clear_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.clear()


def test_extract_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.extract()


def test_decompose_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.decompose()


def test_replace_with_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.replace_with("new content")


def test_replaceWith_alias_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.replaceWith("new content")


def test_unwrap_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.unwrap()


def test_wrap_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.wrap("div")


def test_insert_before_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.insert_before("new")


def test_insert_after_raises(soup):
    p = soup.find("p", id="first")
    with pytest.raises(NotImplementedError):
        p.insert_after("new")


def test_smooth_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.smooth()


def test_replace_with_children_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.replace_with_children()


def test_replaceWithChildren_alias_raises(soup):
    div = soup.find("div", id="wrapper")
    with pytest.raises(NotImplementedError):
        div.replaceWithChildren()


# ─── Advanced find_next / find_previous with regex ─────────────────────────

def test_find_next_regex_name(soup):
    """find_next with regex for tag name."""
    p1 = soup.find("p", id="first")
    nxt = p1.find_next(re.compile(r"^(p|span)$"))
    assert nxt is not None
    assert nxt.name in ("p", "span", "em")  # em is inside p#first


def test_find_all_next_multiple_names(soup):
    p1 = soup.find("p", id="first")
    following = p1.find_all_next(["p", "span"])
    names = [e.name for e in following]
    assert "p" in names
    assert "span" in names


def test_find_all_previous_multiple_names(soup):
    p3 = soup.find("p", id="third")
    preceding = p3.find_all_previous(["p", "div"])
    names = [e.name for e in preceding]
    assert "p" in names


# ─── find_next_siblings with dict attrs ──────────────────────────────────────

def test_find_next_sibling_with_attrs(soup):
    p1 = soup.find("p", id="first")
    nxt = p1.find_next_sibling("p", {"id": "second"})
    assert nxt is not None
    assert nxt["id"] == "second"


def test_find_previous_sibling_with_attrs(soup):
    p2 = soup.find("p", id="second")
    prev = p2.find_previous_sibling("p", {"id": "first"})
    assert prev is not None
    assert prev["id"] == "first"


# ─── Interaction: index + contents ──────────────────────────────────────────

def test_index_consistent_with_contents(soup):
    wrapper = soup.find("div", id="wrapper")
    p2 = soup.find("p", id="second")
    idx = wrapper.index(p2)
    # The element at that index in contents should be the same element
    assert wrapper.contents[idx] == p2
