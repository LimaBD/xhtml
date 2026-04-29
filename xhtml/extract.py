"""
xhtml.extract
~~~~~~~~~~~~~~~~
Structured HTML extraction using Pydantic models.

Define what you want — point fields at CSS selectors — get typed data back::

    from xhtml.extract import HtmlModel, Field
    from typing import List

    class Article(HtmlModel):
        title:   str       = Field(selector="h1")
        url:     str       = Field(selector="a.read-more", attr="href", default="#")
        summary: str       = Field(selector="p.intro",     default="")
        tags:    List[str] = Field(selector=".tag",         multiple=True, default_factory=list)
        price:   float     = Field(
            selector=".price",
            transform=lambda s: float(s.replace("$", "").replace(",", "")),
            default=0.0,
        )

    article  = Article.from_html(html)
    articles = Article.from_html_list(page_html, item_selector="article.post")
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Type, TypeVar, Union

try:
    import pydantic
    from pydantic import BaseModel, ConfigDict
    from pydantic.fields import FieldInfo
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "xhtml.extract requires pydantic>=2.0. "
        "Install it with:  pip install pydantic"
    ) from _exc

from xhtml.element import Xhtml, Tag

__all__ = ["Field", "HtmlModel"]

T = TypeVar("T", bound="HtmlModel")

# Key used to embed xhtml metadata inside a Pydantic FieldInfo
_XHTML_KEY = "__xhtml_meta__"


# ─── Field descriptor ────────────────────────────────────────────────────────


def Field(
    selector: Optional[str] = None,
    *,
    attr: Optional[str] = None,
    multiple: bool = False,
    strip: bool = True,
    transform: Optional[Callable[[str], Any]] = None,
    default: Any = pydantic.fields.PydanticUndefined,
    default_factory: Optional[Callable[[], Any]] = None,
    description: Optional[str] = None,
    **extra_pydantic_kwargs: Any,
) -> Any:
    """Declare an HTML extraction field on an :class:`HtmlModel`.

    Parameters
    ----------
    selector:
        CSS selector that locates the element(s) to extract.
    attr:
        HTML attribute to read (e.g. ``"href"``, ``"src"``).
        When *None* (default) the element's text content is extracted.
    multiple:
        If ``True``, all matching elements are returned as a list.
        The field type should be ``List[...]``.
    strip:
        Strip leading/trailing whitespace from extracted text.  Default ``True``.
    transform:
        Optional callable applied to each raw string before Pydantic validation.
        Useful for type coercion (e.g. ``lambda s: float(s.replace("$", ""))``).
    default:
        Scalar default used when no element is found.
    default_factory:
        Factory for mutable defaults (e.g. ``default_factory=list``).
    description:
        Human-readable field description forwarded to Pydantic / JSON Schema.
    **extra_pydantic_kwargs:
        Any additional keyword arguments are forwarded to ``pydantic.Field()``.
    """
    soup_meta: dict = {
        "selector": selector,
        "attr": attr,
        "multiple": multiple,
        "strip": strip,
        "transform": transform,
    }
    json_schema_extra: dict = {_XHTML_KEY: soup_meta}

    pydantic_kwargs: dict = {"json_schema_extra": json_schema_extra}
    if description is not None:
        pydantic_kwargs["description"] = description
    pydantic_kwargs.update(extra_pydantic_kwargs)

    if default is not pydantic.fields.PydanticUndefined:
        return pydantic.Field(default=default, **pydantic_kwargs)
    if default_factory is not None:
        return pydantic.Field(default_factory=default_factory, **pydantic_kwargs)
    return pydantic.Field(**pydantic_kwargs)


# ─── HtmlModel ───────────────────────────────────────────────────────────────


class HtmlModel(BaseModel):
    """Pydantic model with built-in HTML extraction.

    Subclass this and annotate fields with :func:`Field` to extract
    structured data from HTML in a single call.

    Example
    -------
    ::

        from xhtml.extract import HtmlModel, Field

        class Product(HtmlModel):
            name:  str   = Field(selector="h1.product-name")
            price: float = Field(
                selector=".price",
                transform=lambda s: float(s.replace("$", "")),
            )
            image: str = Field(selector="img.hero", attr="src", default="")

        product = Product.from_html(html)
        print(product.name, product.price)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_html(
        cls: Type[T],
        markup: Union[str, bytes],
        parser: str = "html.parser",
    ) -> T:
        """Parse *markup* and extract model fields.

        Parameters
        ----------
        markup:
            Raw HTML/XML string or bytes.
        parser:
            Parser name forwarded to :class:`~xhtml.Xhtml`
            (default ``"html.parser"``).
        """
        soup = Xhtml(markup, parser)
        return cls._extract_from_tag(soup)

    @classmethod
    def from_tag(cls: Type[T], tag: Tag) -> T:
        """Extract model fields from an already-parsed :class:`~xhtml.Tag`.

        Useful when you are iterating over elements inside an outer loop::

            soup = Xhtml(html, "html.parser")
            for card in soup.select(".card"):
                item = MyModel.from_tag(card)
        """
        return cls._extract_from_tag(tag)

    @classmethod
    def from_html_list(
        cls: Type[T],
        markup: Union[str, bytes],
        item_selector: str,
        parser: str = "html.parser",
    ) -> List[T]:
        """Extract one model per element matched by *item_selector*.

        Useful for pages with repeated structures (search results, product
        listings, feed entries, etc.)::

            results = SearchResult.from_html_list(page_html, ".result-card")

        Parameters
        ----------
        markup:
            Raw HTML/XML string or bytes.
        item_selector:
            CSS selector that identifies each repeating container element.
        parser:
            Parser name forwarded to :class:`~xhtml.Xhtml`.
        """
        soup = Xhtml(markup, parser)
        return [cls._extract_from_tag(el) for el in soup.select(item_selector)]

    # ── Internal ──────────────────────────────────────────────────────────────

    @classmethod
    def _extract_from_tag(cls: Type[T], tag: Tag) -> T:
        data: dict = {}
        for field_name, field_info in cls.model_fields.items():
            meta = _get_meta(field_info)
            if meta is None:
                # Plain Pydantic field with no HTML extraction metadata — skip;
                # Pydantic will apply its own default/required handling.
                continue

            selector: Optional[str] = meta["selector"]
            attr: Optional[str] = meta["attr"]
            multiple: bool = meta["multiple"]
            strip: bool = meta["strip"]
            transform: Optional[Callable] = meta["transform"]

            if selector is None:
                continue

            if multiple:
                elements = tag.select(selector)
                data[field_name] = [
                    _pull_value(el, attr, strip, transform) for el in elements
                ]
            else:
                el = tag.select_one(selector)
                if el is not None:
                    data[field_name] = _pull_value(el, attr, strip, transform)
                # If element not found *and* there is a default, Pydantic handles it.

        return cls(**data)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_meta(field_info: FieldInfo) -> Optional[dict]:
    """Return the xhtml metadata dict embedded in *field_info*, or None."""
    extra = field_info.json_schema_extra
    if isinstance(extra, dict):
        return extra.get(_XHTML_KEY)
    return None


def _pull_value(
    el: Tag,
    attr: Optional[str],
    strip: bool,
    transform: Optional[Callable[[str], Any]],
) -> Any:
    """Extract a single raw value from *el*, then apply *transform*."""
    if attr is not None:
        raw: str = el.get(attr) or ""
    else:
        raw = el.get_text(strip=strip)
    return transform(raw) if transform is not None else raw
