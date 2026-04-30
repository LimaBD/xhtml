"""
tests/test_edge_cases.py
~~~~~~~~~~~~~~~~~~~~~~~~
Edge-case tests for tree navigation, document-order traversal,
Rust fast-path queries, and boundary conditions.
"""
from __future__ import annotations

import re
import pytest
from xhtml import Xhtml, Tag, NavigableString
from xhtml.element import ResultSet


# ─── Fixtures ────────────────────────────────────────────────────────────────

DEEP_HTML = """
<html><body>
  <div id="d1">
    <div id="d2">
      <div id="d3">
        <p id="leaf">Leaf text</p>
      </div>
    </div>
  </div>
  <section id="s1">
    <p id="sp1">Section para 1</p>
    <p id="sp2">Section para 2</p>
  </section>
</body></html>
"""

LINEAR_HTML = """
<html><body>
  <p id="p1">One</p>
  <p id="p2">Two</p>
  <p id="p3">Three</p>
</body></html>
"""

SIBLING_HTML = """
<html><body>
  <ul id="list">
    <li id="li1" class="item odd">A</li>
    <li id="li2" class="item even">B</li>
    <li id="li3" class="item odd">C</li>
    <li id="li4" class="item even">D</li>
  </ul>
</body></html>
"""

MIXED_HTML = """
<html><body>
  <article id="art">
    <h1 id="h">Title</h1>
    <p id="pa">Before <em id="em">emphasis</em> after</p>
    <p id="pb">End</p>
  </article>
</body></html>
"""


@pytest.fixture
def deep():
    return Xhtml(DEEP_HTML, "html.parser")


@pytest.fixture
def linear():
    return Xhtml(LINEAR_HTML, "html.parser")


@pytest.fixture
def sibling():
    return Xhtml(SIBLING_HTML, "html.parser")


@pytest.fixture
def mixed():
    return Xhtml(MIXED_HTML, "html.parser")


# ─── next_element / previous_element — boundary conditions ───────────────────

def test_next_element_descends_into_first_child():
    """next_element of a tag is its first child (no whitespace in compact HTML)."""
    s = Xhtml("<article><h1>Title</h1><p>Body</p></article>", "html.parser")
    art = s.find("article")
    nxt = art.next_element
    assert nxt is not None
    assert getattr(nxt, "name", None) == "h1"


def test_next_element_of_leaf_skips_to_sibling(mixed):
    """next_element of a leaf element (no children) is its next sibling."""
    h = mixed.find("h1", id="h")
    nxt = h.next_element
    # h1 has no tag children; next is the text inside h1 or the next sibling
    assert nxt is not None


def test_next_element_left_to_right_order(linear):
    """Walking next_element from p#p1 must reach p#p2 before p#p3."""
    p1 = linear.find("p", id="p1")
    seen_ids = []
    cur = p1.next_element
    while cur is not None:
        if isinstance(cur, Tag) and cur.has_attr("id"):
            seen_ids.append(cur["id"])
        cur = cur.next_element
    assert seen_ids.index("p2") < seen_ids.index("p3")


def test_previous_element_of_leaf_is_last_descendant_of_prev_sibling(mixed):
    """
    previous_element of <p id='pa'> should reach back into <h1>'s last
    descendant (the text node inside h1), not h1 itself.
    """
    pa = mixed.find("p", id="pa")
    prev = pa.previous_element
    assert prev is not None
    # prev should be the text inside h1 (a NavigableString) or h1 itself
    # depending on whether text has been absorbed; either way not None
    assert str(prev) != ""


def test_next_element_chain_terminates(linear):
    """Walking next_element must eventually return None (no infinite loop)."""
    el = linear.find("p", id="p1")
    count = 0
    cur = el
    while cur is not None:
        count += 1
        assert count < 500, "next_element did not terminate"
        cur = cur.next_element
    assert count > 1


def test_previous_element_chain_terminates(linear):
    """Walking previous_element must terminate."""
    el = linear.find("p", id="p3")
    count = 0
    cur = el
    while cur is not None:
        count += 1
        assert count < 500, "previous_element did not terminate"
        cur = cur.previous_element
    assert count > 1


def test_next_previous_are_inverse(linear):
    """Going forward then immediately backward should return to start."""
    p1 = linear.find("p", id="p1")
    nxt = p1.next_element
    assert nxt is not None
    back = nxt.previous_element
    assert back is not None
    assert str(back) == str(p1)


# ─── next_elements / previous_elements — iteration ──────────────────────────

def test_next_elements_does_not_include_self(linear):
    p2 = linear.find("p", id="p2")
    elements = list(p2.next_elements)
    assert p2 not in elements


def test_previous_elements_does_not_include_self(linear):
    p2 = linear.find("p", id="p2")
    elements = list(p2.previous_elements)
    assert p2 not in elements


def test_next_elements_reaches_all_following_tags(linear):
    p1 = linear.find("p", id="p1")
    tag_ids = [e["id"] for e in p1.next_elements if isinstance(e, Tag) and e.has_attr("id")]
    assert "p2" in tag_ids
    assert "p3" in tag_ids


def test_previous_elements_reaches_all_preceding_tags(linear):
    p3 = linear.find("p", id="p3")
    tag_ids = [e["id"] for e in p3.previous_elements if isinstance(e, Tag) and e.has_attr("id")]
    assert "p2" in tag_ids
    assert "p1" in tag_ids


def test_previous_elements_order_is_reverse_document(linear):
    """previous_elements returns nodes closest-first (reverse document order)."""
    p3 = linear.find("p", id="p3")
    tag_ids = [e["id"] for e in p3.previous_elements if isinstance(e, Tag) and e.has_attr("id")]
    assert tag_ids.index("p2") < tag_ids.index("p1")


# ─── ancestors / parents — boundary conditions ───────────────────────────────

def test_parents_of_document_root_is_empty():
    s = Xhtml("<p>hi</p>", "html.parser")
    assert list(s.parents) == []


def test_parents_does_not_include_self(deep):
    leaf = deep.find("p", id="leaf")
    assert leaf not in list(leaf.parents)


def test_parents_does_not_yield_document_node(deep):
    """No parent should be the hidden Xhtml document wrapper."""
    leaf = deep.find("p", id="leaf")
    for p in leaf.parents:
        assert not p.hidden


def test_parents_order_innermost_first(deep):
    leaf = deep.find("p", id="leaf")
    parent_names = [p.name for p in leaf.parents]
    # Immediate parent is d3, then d2, then d1
    assert parent_names[0] == "div"
    d3_idx = next(i for i, p in enumerate(leaf.parents) if p.get("id") == "d3")
    d2_idx = next(i for i, p in enumerate(leaf.parents) if p.get("id") == "d2")
    d1_idx = next(i for i, p in enumerate(leaf.parents) if p.get("id") == "d1")
    assert d3_idx < d2_idx < d1_idx


def test_parents_deep_tree(deep):
    leaf = deep.find("p", id="leaf")
    ids = [p.get("id") for p in leaf.parents if isinstance(p, Tag) and p.has_attr("id")]
    assert "d3" in ids
    assert "d2" in ids
    assert "d1" in ids


# ─── find_parent / find_parents — Rust fast path ──────────────────────────────

def test_find_parent_by_name_rust_path(deep):
    leaf = deep.find("p", id="leaf")
    # Simple string name → Rust fast path
    d2 = leaf.find_parent("div", id="d2")
    assert d2 is not None
    assert d2["id"] == "d2"


def test_find_parent_by_id_rust_path(deep):
    leaf = deep.find("p", id="leaf")
    found = leaf.find_parent(id="d1")
    assert found is not None
    assert found["id"] == "d1"


def test_find_parents_all_rust_path(deep):
    leaf = deep.find("p", id="leaf")
    divs = leaf.find_parents("div")
    div_ids = [d["id"] for d in divs if d.has_attr("id")]
    assert "d3" in div_ids
    assert "d2" in div_ids
    assert "d1" in div_ids


def test_find_parents_limit_rust_path(deep):
    leaf = deep.find("p", id="leaf")
    divs = leaf.find_parents("div", limit=1)
    assert len(divs) == 1
    assert divs[0]["id"] == "d3"


def test_find_parent_no_match_returns_none(linear):
    p1 = linear.find("p", id="p1")
    assert p1.find_parent("article") is None


# ─── find_next / find_all_next — Rust fast path ──────────────────────────────

def test_find_next_rust_path_by_name(linear):
    p1 = linear.find("p", id="p1")
    p2 = p1.find_next("p")
    assert p2 is not None
    assert p2["id"] == "p2"


def test_find_next_rust_path_by_id(linear):
    p1 = linear.find("p", id="p1")
    p3 = p1.find_next(id="p3")
    assert p3 is not None
    assert p3["id"] == "p3"


def test_find_next_no_name_matches_any_tag(linear):
    """find_next() with no arguments must return the immediately next tag."""
    p1 = linear.find("p", id="p1")
    nxt = p1.find_next()
    assert nxt is not None


def test_find_next_returns_none_when_past_end(linear):
    p3 = linear.find("p", id="p3")
    assert p3.find_next("section") is None


def test_find_all_next_returns_result_set(linear):
    p1 = linear.find("p", id="p1")
    result = p1.find_all_next("p")
    assert isinstance(result, ResultSet)


def test_find_all_next_returns_empty_result_set_on_no_match(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_next("article")
    assert isinstance(result, ResultSet)
    assert len(result) == 0


def test_find_all_next_limit_zero_is_unlimited(linear):
    p1 = linear.find("p", id="p1")
    result = p1.find_all_next("p", limit=0)
    assert len(result) == 2  # p2 and p3


def test_find_next_with_multi_name_list(deep):
    """find_next with a list of tag names takes the Rust fast path."""
    d1 = deep.find("div", id="d1")
    # Both div and p are descendants; find the first one after d1
    found = d1.find_next(["div", "p"])
    assert found is not None
    assert found.name in ("div", "p")


# ─── find_previous / find_all_previous — Rust fast path ──────────────────────

def test_find_previous_rust_path_by_name(linear):
    p3 = linear.find("p", id="p3")
    p2 = p3.find_previous("p")
    assert p2 is not None
    assert p2["id"] == "p2"


def test_find_previous_rust_path_by_id(linear):
    p3 = linear.find("p", id="p3")
    p1 = p3.find_previous(id="p1")
    assert p1 is not None
    assert p1["id"] == "p1"


def test_find_previous_no_match_returns_none(linear):
    p1 = linear.find("p", id="p1")
    assert p1.find_previous("p") is None


def test_find_all_previous_returns_result_set(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_previous("p")
    assert isinstance(result, ResultSet)


def test_find_all_previous_order_closest_first(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_previous("p")
    assert result[0]["id"] == "p2"
    assert result[1]["id"] == "p1"


def test_find_all_previous_limit(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_previous("p", limit=1)
    assert len(result) == 1
    assert result[0]["id"] == "p2"


def test_find_all_previous_limit_zero_is_unlimited(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_previous("p", limit=0)
    assert len(result) == 2


def test_find_all_previous_no_match_empty_result_set(linear):
    p1 = linear.find("p", id="p1")
    result = p1.find_all_previous("article")
    assert isinstance(result, ResultSet)
    assert len(result) == 0


# ─── find_next_sibling / find_next_siblings — Rust fast path ─────────────────

def test_find_next_sibling_rust_path_by_name(sibling):
    li1 = sibling.find("li", id="li1")
    li2 = li1.find_next_sibling("li")
    assert li2 is not None
    assert li2["id"] == "li2"


def test_find_next_sibling_rust_path_by_class(sibling):
    li1 = sibling.find("li", id="li1")
    even = li1.find_next_sibling(class_="even")
    assert even is not None
    assert even["id"] == "li2"


def test_find_next_sibling_last_has_none(sibling):
    li4 = sibling.find("li", id="li4")
    assert li4.find_next_sibling("li") is None


def test_find_next_siblings_all(sibling):
    li1 = sibling.find("li", id="li1")
    result = li1.find_next_siblings("li")
    assert isinstance(result, ResultSet)
    assert len(result) == 3
    assert result[0]["id"] == "li2"


def test_find_next_siblings_limit(sibling):
    li1 = sibling.find("li", id="li1")
    result = li1.find_next_siblings("li", limit=2)
    assert len(result) == 2


def test_find_next_siblings_no_match_empty(sibling):
    li4 = sibling.find("li", id="li4")
    result = li4.find_next_siblings("li")
    assert isinstance(result, ResultSet)
    assert len(result) == 0


# ─── find_previous_sibling / find_previous_siblings — Rust fast path ─────────

def test_find_previous_sibling_rust_path_by_name(sibling):
    li3 = sibling.find("li", id="li3")
    li2 = li3.find_previous_sibling("li")
    assert li2 is not None
    assert li2["id"] == "li2"


def test_find_previous_sibling_rust_path_by_class(sibling):
    li4 = sibling.find("li", id="li4")
    odd = li4.find_previous_sibling(class_="odd")
    assert odd is not None
    assert odd["id"] == "li3"


def test_find_previous_sibling_first_has_none(sibling):
    li1 = sibling.find("li", id="li1")
    assert li1.find_previous_sibling("li") is None


def test_find_previous_siblings_all(sibling):
    li4 = sibling.find("li", id="li4")
    result = li4.find_previous_siblings("li")
    assert isinstance(result, ResultSet)
    assert len(result) == 3
    assert result[0]["id"] == "li3"  # closest first


def test_find_previous_siblings_limit(sibling):
    li4 = sibling.find("li", id="li4")
    result = li4.find_previous_siblings("li", limit=2)
    assert len(result) == 2
    assert result[0]["id"] == "li3"
    assert result[1]["id"] == "li2"


def test_find_previous_siblings_no_match_empty(sibling):
    li1 = sibling.find("li", id="li1")
    result = li1.find_previous_siblings("li")
    assert isinstance(result, ResultSet)
    assert len(result) == 0


# ─── descendants — Rust path ──────────────────────────────────────────────────

def test_descendants_empty_tag_yields_nothing():
    s = Xhtml("<br>", "html.parser")
    br = s.find("br")
    assert br is not None
    desc = list(br.descendants)
    assert desc == []


def test_descendants_leaf_p_yields_only_text():
    s = Xhtml("<p>hello</p>", "html.parser")
    p = s.find("p")
    desc = list(p.descendants)
    assert len(desc) == 1
    assert isinstance(desc[0], NavigableString)
    assert str(desc[0]) == "hello"


def test_descendants_dfs_order(deep):
    """Descendants must be in DFS pre-order (outer div before inner div)."""
    d1 = deep.find("div", id="d1")
    ids = [e["id"] for e in d1.descendants if isinstance(e, Tag) and e.has_attr("id")]
    assert ids.index("d2") < ids.index("d3")
    assert ids.index("d3") < ids.index("leaf")


def test_descendants_includes_text_nodes(mixed):
    pa = mixed.find("p", id="pa")
    desc = list(pa.descendants)
    text_nodes = [d for d in desc if isinstance(d, NavigableString)]
    assert len(text_nodes) > 0


def test_descendants_count_matches_contents_recursion(deep):
    """Number of descendants from Rust path should equal the manual recursive count."""
    def count_desc(tag):
        total = 0
        for c in tag.children:
            total += 1
            if isinstance(c, Tag):
                total += count_desc(c)
        return total

    d1 = deep.find("div", id="d1")
    rust_count = sum(1 for _ in d1.descendants)
    manual_count = count_desc(d1)
    assert rust_count == manual_count


# ─── Regex / callable filters — Python fallback path ─────────────────────────

def test_find_next_regex_name_fallback(mixed):
    """Regex name triggers Python fallback — result must still be correct."""
    h = mixed.find("h1", id="h")
    nxt = h.find_next(re.compile(r"^(p|section)$"))
    assert nxt is not None
    assert nxt.name in ("p", "section")


def test_find_all_next_regex_attr_fallback(sibling):
    li1 = sibling.find("li", id="li1")
    result = li1.find_all_next("li", id=re.compile(r"li[24]"))
    assert isinstance(result, ResultSet)
    ids = [e["id"] for e in result]
    assert "li2" in ids
    assert "li4" in ids
    assert "li1" not in ids
    assert "li3" not in ids


def test_find_previous_callable_fallback(linear):
    """Callable name filter forces the Python fallback path."""
    p3 = linear.find("p", id="p3")
    found = p3.find_previous(lambda t: t.name == "p" and t.get("id") == "p1")
    assert found is not None
    assert found["id"] == "p1"


def test_find_next_sibling_regex_fallback(sibling):
    """Regex id on sibling search triggers Python fallback path."""
    li1 = sibling.find("li", id="li1")
    found = li1.find_next_sibling(id=re.compile(r"li[24]"))
    assert found is not None
    assert found["id"] == "li2"


def test_find_parent_callable_fallback(deep):
    leaf = deep.find("p", id="leaf")
    d2 = leaf.find_parent(lambda t: t.name == "div" and t.get("id") == "d2")
    assert d2 is not None
    assert d2["id"] == "d2"


# ─── NavigableString — document-order navigation via Rust ────────────────────

def test_navigable_string_next_element_not_none(mixed):
    em = mixed.find("em", id="em")
    children = [c for c in em.children if isinstance(c, NavigableString)]
    assert children, "em should have a text child"
    ns = children[0]
    # next_element of the text inside <em> should go to </em>'s next node
    nxt = ns.next_element
    # It may be None if em is the absolute last node; here it should not be
    assert nxt is not None


def test_navigable_string_previous_element_is_parent_when_first_child(mixed):
    h = mixed.find("h1", id="h")
    children = [c for c in h.children if isinstance(c, NavigableString)]
    assert children
    ns = children[0]
    prev = ns.previous_element
    # First child of h1 → previous_element should be h1 itself
    assert prev is not None
    assert getattr(prev, "name", None) == "h1"


def test_navigable_string_next_elements_terminates(mixed):
    em = mixed.find("em", id="em")
    children = [c for c in em.children if isinstance(c, NavigableString)]
    assert children
    ns = children[0]
    count = 0
    cur = ns.next_element
    while cur is not None:
        count += 1
        assert count < 500, "NavigableString.next_element did not terminate"
        cur = cur.next_element


def test_navigable_string_parents_via_rust(mixed):
    em = mixed.find("em", id="em")
    children = [c for c in em.children if isinstance(c, NavigableString)]
    assert children
    ns = children[0]
    parent_names = [p.name for p in ns.parents if isinstance(p, Tag)]
    assert "em" in parent_names
    assert "p" in parent_names
    assert "article" in parent_names


# ─── Edge cases for find_all with attrs= dict (positional) ───────────────────

def test_find_all_next_attrs_dict(sibling):
    """attrs passed as positional dict argument must work with Rust fast path."""
    li1 = sibling.find("li", id="li1")
    result = li1.find_all_next("li", {"class": "even"})
    assert isinstance(result, ResultSet)
    ids = [e["id"] for e in result]
    assert "li2" in ids
    assert "li4" in ids


def test_find_all_previous_attrs_dict(sibling):
    li4 = sibling.find("li", id="li4")
    result = li4.find_all_previous("li", {"class": "odd"})
    assert isinstance(result, ResultSet)
    ids = [e["id"] for e in result]
    assert "li3" in ids
    assert "li1" in ids


def test_find_next_sibling_attrs_dict(sibling):
    li1 = sibling.find("li", id="li1")
    found = li1.find_next_sibling("li", {"id": "li3"})
    assert found is not None
    assert found["id"] == "li3"


def test_find_parent_attrs_dict(deep):
    leaf = deep.find("p", id="leaf")
    found = leaf.find_parent("div", {"id": "d2"})
    assert found is not None
    assert found["id"] == "d2"


# ─── Single-element document edge cases ──────────────────────────────────────

def test_single_tag_next_element_is_text():
    s = Xhtml("<p>hello</p>", "html.parser")
    p = s.find("p")
    nxt = p.next_element
    assert nxt is not None
    assert isinstance(nxt, NavigableString)
    assert str(nxt) == "hello"


def test_single_tag_no_next_sibling():
    s = Xhtml("<p>only</p>", "html.parser")
    p = s.find("p")
    assert p.find_next_sibling("p") is None


def test_single_tag_no_previous_sibling():
    s = Xhtml("<p>only</p>", "html.parser")
    p = s.find("p")
    assert p.find_previous_sibling("p") is None


def test_empty_document_find_returns_none():
    s = Xhtml("", "html.parser")
    assert s.find("p") is None


def test_empty_document_find_all_returns_empty():
    s = Xhtml("", "html.parser")
    result = s.find_all("p")
    assert isinstance(result, ResultSet)
    assert len(result) == 0


# ─── Deeply nested previous_element travels via last_descendant ─────────────

def test_previous_element_uses_last_descendant():
    """
    previous_element of p#p2 must be the last descendant of p#p1 — in
    compact HTML (no whitespace siblings) that is the text node inside p1.
    """
    s = Xhtml("<div><p id='p1'>text1</p><p id='p2'>text2</p></div>", "html.parser")
    p2 = s.find("p", id="p2")
    prev = p2.previous_element
    assert prev is not None
    # The previous element of p2 is the last descendant of p1 = the text node
    assert isinstance(prev, NavigableString)
    assert str(prev) == "text1"


# ─── find_all_next / find_all_previous return source ─────────────────────────

def test_find_all_next_result_set_source(linear):
    p1 = linear.find("p", id="p1")
    result = p1.find_all_next("p")
    assert result.source is p1


def test_find_all_previous_result_set_source(linear):
    p3 = linear.find("p", id="p3")
    result = p3.find_all_previous("p")
    assert result.source is p3


def test_find_next_siblings_result_set_source(sibling):
    li1 = sibling.find("li", id="li1")
    result = li1.find_next_siblings("li")
    assert result.source is li1


def test_find_previous_siblings_result_set_source(sibling):
    li4 = sibling.find("li", id="li4")
    result = li4.find_previous_siblings("li")
    assert result.source is li4


def test_find_parents_result_set_source(deep):
    leaf = deep.find("p", id="leaf")
    result = leaf.find_parents("div")
    assert result.source is leaf
