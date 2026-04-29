"""
tests/test_extract.py
~~~~~~~~~~~~~~~~~~~~~
Tests for xhtml.extract — Pydantic-based structured HTML extraction.
"""

from __future__ import annotations

import pytest
from typing import List, Optional

pytest.importorskip("pydantic")

from xhtml import Xhtml, Tag
from xhtml.extract import Field, HtmlModel


# ─── Fixtures ─────────────────────────────────────────────────────────────────

PRODUCT_HTML = """
<html><body>
  <h1 class="product-name">Rust in Action</h1>
  <span class="price">$29.99</span>
  <img class="hero" src="/images/ria.jpg" alt="cover">
  <p class="description">A hands-on guide to systems programming with Rust.</p>
  <ul class="tags">
    <li class="tag">rust</li>
    <li class="tag">systems</li>
    <li class="tag">programming</li>
  </ul>
  <a class="buy-btn" href="/buy/ria">Buy now</a>
  <span class="stock-badge">In Stock</span>
</body></html>
"""

LISTING_HTML = """
<html><body>
  <div class="card">
    <h2>Alpha</h2>
    <a href="/alpha">Read</a>
    <p class="desc">First post.</p>
  </div>
  <div class="card">
    <h2>Beta</h2>
    <a href="/beta">Read</a>
    <p class="desc">Second post.</p>
  </div>
  <div class="card">
    <h2>Gamma</h2>
    <a href="/gamma">Read</a>
  </div>
</body></html>
"""

MINIMAL_HTML = "<html><body><p>hello</p></body></html>"


# ─── Simple model ────────────────────────────────────────────────────────────


class Product(HtmlModel):
    name: str = Field(selector="h1.product-name")
    description: str = Field(selector="p.description", default="")
    image: str = Field(selector="img.hero", attr="src", default="")
    buy_link: str = Field(selector="a.buy-btn", attr="href", default="#")
    tags: List[str] = Field(selector=".tag", multiple=True, default_factory=list)
    price: float = Field(
        selector=".price",
        transform=lambda s: float(s.replace("$", "").replace(",", "")),
    )
    in_stock: bool = Field(
        selector=".stock-badge",
        transform=lambda s: "in stock" in s.lower(),
        default=False,
    )


class Card(HtmlModel):
    title: str = Field(selector="h2")
    url: str = Field(selector="a", attr="href", default="")
    desc: str = Field(selector="p.desc", default="")


# ─── from_html ───────────────────────────────────────────────────────────────


def test_from_html_text_field():
    p = Product.from_html(PRODUCT_HTML)
    assert p.name == "Rust in Action"


def test_from_html_attr_field():
    p = Product.from_html(PRODUCT_HTML)
    assert p.image == "/images/ria.jpg"
    assert p.buy_link == "/buy/ria"


def test_from_html_multiple_field():
    p = Product.from_html(PRODUCT_HTML)
    assert p.tags == ["rust", "systems", "programming"]


def test_from_html_transform_float():
    p = Product.from_html(PRODUCT_HTML)
    assert p.price == pytest.approx(29.99)


def test_from_html_transform_bool():
    p = Product.from_html(PRODUCT_HTML)
    assert p.in_stock is True


def test_from_html_default_for_missing_element():
    """Fields with explicit defaults return those defaults when no element is found."""

    class Defaults(HtmlModel):
        name: str = Field(selector="h1.missing", default="")
        image: str = Field(selector="img.missing", attr="src", default="")
        buy_link: str = Field(selector="a.missing", attr="href", default="#")
        tags: List[str] = Field(selector=".missing-tag", multiple=True, default_factory=list)
        in_stock: bool = Field(selector=".missing-badge", default=False)

    p = Defaults.from_html(MINIMAL_HTML)
    assert p.name == ""
    assert p.image == ""
    assert p.buy_link == "#"
    assert p.tags == []
    assert p.in_stock is False


def test_from_html_description():
    p = Product.from_html(PRODUCT_HTML)
    assert "Rust" in p.description


def test_from_html_bytes_input():
    p = Product.from_html(PRODUCT_HTML.encode())
    assert p.name == "Rust in Action"


def test_from_html_pydantic_type_coercion():
    """Pydantic coerces the raw string to the declared type."""
    p = Product.from_html(PRODUCT_HTML)
    assert isinstance(p.price, float)


# ─── from_tag ────────────────────────────────────────────────────────────────


def test_from_tag_basic():
    soup = Xhtml(PRODUCT_HTML, "html.parser")
    p = Product.from_tag(soup)
    assert p.name == "Rust in Action"
    assert p.price == pytest.approx(29.99)


def test_from_tag_scoped_extraction():
    """Scoping to a sub-tag should only see elements within it."""
    html = """
    <html><body>
      <div id="outer">
        <h2>Outer title</h2>
        <div id="inner">
          <h2>Inner title</h2>
        </div>
      </div>
    </body></html>
    """

    class TitleModel(HtmlModel):
        title: str = Field(selector="h2")

    soup = Xhtml(html, "html.parser")
    inner_div = soup.find(id="inner")
    m = TitleModel.from_tag(inner_div)
    assert m.title == "Inner title"


# ─── from_html_list ──────────────────────────────────────────────────────────


def test_from_html_list_count():
    cards = Card.from_html_list(LISTING_HTML, ".card")
    assert len(cards) == 3


def test_from_html_list_values():
    cards = Card.from_html_list(LISTING_HTML, ".card")
    assert cards[0].title == "Alpha"
    assert cards[1].title == "Beta"
    assert cards[2].title == "Gamma"


def test_from_html_list_attr():
    cards = Card.from_html_list(LISTING_HTML, ".card")
    assert cards[0].url == "/alpha"
    assert cards[1].url == "/beta"
    assert cards[2].url == "/gamma"


def test_from_html_list_default_for_missing():
    cards = Card.from_html_list(LISTING_HTML, ".card")
    # Gamma card has no <p class="desc">
    assert cards[2].desc == ""


def test_from_html_list_empty_selector():
    cards = Card.from_html_list(MINIMAL_HTML, ".card")
    assert cards == []


# ─── Field options ───────────────────────────────────────────────────────────


def test_field_strip_whitespace():
    html = "<html><body><p>  hello  </p></body></html>"

    class M(HtmlModel):
        text: str = Field(selector="p", strip=True, default="")

    assert M.from_html(html).text == "hello"


def test_field_strip_false():
    html = "<html><body><p>  hello  </p></body></html>"

    class M(HtmlModel):
        text: str = Field(selector="p", strip=False, default="")

    assert M.from_html(html).text == "  hello  "


def test_field_multiple_empty():
    html = "<html><body></body></html>"

    class M(HtmlModel):
        items: List[str] = Field(selector=".item", multiple=True, default_factory=list)

    assert M.from_html(html).items == []


def test_field_attr_missing_returns_empty_string():
    html = "<html><body><a>no href</a></body></html>"

    class M(HtmlModel):
        link: str = Field(selector="a", attr="href", default="")

    # get() returns "" when attribute absent
    assert M.from_html(html).link == ""


def test_field_transform_applied_to_multiple():
    html = """
    <html><body>
      <span class="num">1 </span>
      <span class="num"> 2</span>
      <span class="num">3</span>
    </body></html>
    """

    class M(HtmlModel):
        nums: List[int] = Field(
            selector=".num",
            multiple=True,
            transform=lambda s: int(s.strip()),
            default_factory=list,
        )

    assert M.from_html(html).nums == [1, 2, 3]


def test_field_description_forwarded():
    """description kwarg should not cause errors and is stored in field schema."""

    class M(HtmlModel):
        title: str = Field(selector="h1", default="", description="Page title")

    info = M.model_fields["title"]
    assert info.description == "Page title"


# ─── Pydantic validation ──────────────────────────────────────────────────────


def test_pydantic_required_field_raises():
    """A Field with no default raises ValidationError when element is absent."""
    from pydantic import ValidationError

    class M(HtmlModel):
        required: str = Field(selector="h1.missing-class")

    with pytest.raises(ValidationError):
        M.from_html(MINIMAL_HTML)


def test_pydantic_optional_field():
    class M(HtmlModel):
        opt: Optional[str] = Field(selector="h1.missing", default=None)

    m = M.from_html(MINIMAL_HTML)
    assert m.opt is None


def test_pydantic_model_is_mutable_by_default():
    """Pydantic v2 models are mutable unless ConfigDict(frozen=True) is set."""
    p = Product.from_html(PRODUCT_HTML)
    original = p.name
    p.name = "changed"
    assert p.name == "changed"
    p.name = original  # restore


def test_pydantic_model_dict():
    p = Product.from_html(PRODUCT_HTML)
    d = p.model_dump()
    assert d["name"] == "Rust in Action"
    assert d["price"] == pytest.approx(29.99)


def test_pydantic_model_json_serializable():
    import json

    p = Product.from_html(PRODUCT_HTML)
    raw = p.model_dump_json()
    data = json.loads(raw)
    assert data["name"] == "Rust in Action"


# ─── Edge cases ───────────────────────────────────────────────────────────────


def test_model_with_no_xhtml_fields():
    """A plain Pydantic model without Field() selectors works fine."""

    class Plain(HtmlModel):
        value: int = 42

    m = Plain.from_html(MINIMAL_HTML)
    assert m.value == 42


def test_none_selector_field_is_skipped():
    """Field(selector=None) is ignored during extraction."""

    class M(HtmlModel):
        ignore: str = Field(selector=None, default="fallback")

    assert M.from_html(MINIMAL_HTML).ignore == "fallback"


def test_large_multiple_extraction():
    items = "\n".join(f'<li class="item">{i}</li>' for i in range(100))
    html = f"<html><body><ul>{items}</ul></body></html>"

    class M(HtmlModel):
        nums: List[int] = Field(
            selector=".item",
            multiple=True,
            transform=int,
            default_factory=list,
        )

    m = M.from_html(html)
    assert len(m.nums) == 100
    assert m.nums[0] == 0
    assert m.nums[99] == 99
