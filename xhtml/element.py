"""
xhtml.element
~~~~~~~~~~~~~~~~
Python API layer — Tag, NavigableString, and Xhtml.

All tree operations delegate to the Rust extension (_core), keeping
Python out of the hot path for parsing, searching, and navigation.
"""

from __future__ import annotations

import re
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Union,
)

from xhtml._core import RustDocument, RustNode, RustQuery  # type: ignore[import]


# ─── Query normalisation ─────────────────────────────────────────────────────

def _normalize_query(
    name: Any = None,
    attrs: Optional[Dict[str, Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    recursive: bool = True,
) -> RustQuery:
    """Convert find/find_all keyword arguments into a RustQuery."""
    attrs = dict(attrs or {})
    kwargs = dict(kwargs or {})

    # class_ is used to avoid the Python reserved word 'class'
    class_arg = kwargs.pop("class_", None)
    if class_arg is None:
        class_arg = attrs.pop("class", None)

    id_arg = kwargs.pop("id", None)
    if id_arg is None:
        id_arg = attrs.pop("id", None)

    # Merge remaining filters
    all_attrs = {**attrs, **kwargs}

    # --- Normalise classes ---
    classes: List[str] = []
    if class_arg is not None:
        if isinstance(class_arg, str):
            classes = class_arg.split()
        elif isinstance(class_arg, (list, tuple)):
            classes = [str(c) for c in class_arg]

    # --- Normalise id ---
    id_str: Optional[str] = None
    if id_arg is not None and id_arg is not True:
        id_str = str(id_arg)

    # --- Normalise attribute filters ---
    normalized_attrs: List[tuple] = []
    for k, v in all_attrs.items():
        if v is True:
            # attr must exist, any value
            normalized_attrs.append((k, []))
        elif v is False or v is None:
            pass  # skip (complex "not present" filter handled in Python)
        elif isinstance(v, str):
            normalized_attrs.append((k, [v]))
        elif isinstance(v, (list, tuple)):
            normalized_attrs.append((k, [str(x) for x in v]))
        elif hasattr(v, "match"):
            # regex — handled as post-filter, pass empty list to match all
            normalized_attrs.append((k, []))
        else:
            normalized_attrs.append((k, [str(v)]))

    # --- Normalise tag name(s) ---
    names: List[str] = []
    if name is not None and name is not True:
        if isinstance(name, str):
            names = [name]
        elif isinstance(name, (list, tuple)):
            names = [str(n) for n in name]
        # callable / type → handled in Python, don't filter by name in Rust

    return RustQuery(
        names=names,
        attrs=normalized_attrs,
        classes=classes,
        id=id_str,
        recursive=recursive,
    )


def _attr_value_matches(val: str, filter_val: Any) -> bool:
    """Check if an attribute value matches a filter (str, list, bool, regex)."""
    if filter_val is True:
        return True
    if isinstance(filter_val, str):
        return val == filter_val
    if isinstance(filter_val, (list, tuple)):
        return val in [str(v) for v in filter_val]
    if hasattr(filter_val, "search"):
        return bool(filter_val.search(val))
    return str(filter_val) == val


def _pop_regex_filters(
    attrs: Dict[str, Any], kwargs: Dict[str, Any]
) -> tuple:
    """
    Extract class_ and id from attrs/kwargs.
    If they are regexes, return them as post-filters and do NOT pass to Rust.
    Returns (class_regex, id_regex, attrs, kwargs) — attrs/kwargs are copies.
    """
    attrs = dict(attrs)
    kwargs = dict(kwargs)

    class_arg = kwargs.pop("class_", None)
    if class_arg is None:
        class_arg = attrs.pop("class", None)
    class_regex = class_arg if hasattr(class_arg, "search") else None
    if class_arg is not None and class_regex is None:
        kwargs["class_"] = class_arg  # pass to Rust as normal

    id_arg = kwargs.pop("id", None)
    if id_arg is None:
        id_arg = attrs.pop("id", None)
    id_regex = id_arg if hasattr(id_arg, "search") else None
    if id_arg is not None and id_regex is None:
        kwargs["id"] = id_arg  # pass to Rust as normal

    return class_regex, id_regex, attrs, kwargs


def _apply_extra_filters(
    tags: List["Tag"],
    class_regex: Any,
    id_regex: Any,
) -> List["Tag"]:
    if class_regex:
        tags = [t for t in tags if class_regex.search(t._node.get_attr("class") or "")]
    if id_regex:
        tags = [t for t in tags if id_regex.search(t._node.get_attr("id") or "")]
    return tags


# ─── NavigableString ─────────────────────────────────────────────────────────

class NavigableString(str):
    """
    A text node inside the HTML tree.
    Inherits from str so it can be used directly as a string.
    """

    def __new__(cls, rust_node: Optional[RustNode] = None, text: Optional[str] = None):
        if rust_node is not None:
            text = rust_node.text_content()
        instance = super().__new__(cls, text or "")
        instance._node = rust_node
        return instance

    @property
    def parent(self) -> Optional["Tag"]:
        if self._node:
            p = self._node.parent()
            return Tag(p) if p is not None else None
        return None

    @property
    def next_sibling(self) -> Optional[Any]:
        if self._node:
            sib = self._node.next_sibling()
            if sib is None:
                return None
            return Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)
        return None

    @property
    def previous_sibling(self) -> Optional[Any]:
        if self._node:
            sib = self._node.prev_sibling()
            if sib is None:
                return None
            return Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)
        return None

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        text = str(self)
        return text.strip() if strip else text

    @property
    def text(self) -> str:
        return str(self)

    def __repr__(self) -> str:  # type: ignore[override]
        return repr(str(self))


# ─── Tag ─────────────────────────────────────────────────────────────────────

class Tag:
    """
    Represents an HTML element in the parse tree.

    Wraps a Rust node and exposes a high-level Python API for attribute
    access, text extraction, CSS selectors, and tree navigation.
    """

    def __init__(self, rust_node: RustNode) -> None:
        self._node = rust_node

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._node.name()

    @name.setter
    def name(self, value: str) -> None:
        raise NotImplementedError(
            "xhtml v0.x: in-place tree modification is not yet supported."
        )

    # ── Attribute access ──────────────────────────────────────────────────────

    @property
    def attrs(self) -> Dict[str, Any]:
        raw = dict(self._node.attrs())
        # class attribute is returned as a list
        if "class" in raw:
            raw["class"] = raw["class"].split()
        return raw

    def __getitem__(self, key: str) -> Any:
        val = self._node.get_attr(key)
        if val is None:
            raise KeyError(key)
        if key == "class":
            return val.split()
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        raise NotImplementedError(
            "xhtml v0.x: in-place tree modification is not yet supported."
        )

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError(
            "xhtml v0.x: in-place tree modification is not yet supported."
        )

    def get(self, key: str, default: Any = None) -> Any:
        val = self._node.get_attr(key)
        if val is None:
            return default
        if key == "class":
            return val.split()
        return val

    def has_attr(self, key: str) -> bool:
        return self._node.has_attr(key)

    # ── Text retrieval ────────────────────────────────────────────────────────

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        return self._node.get_text(separator, strip)

    @property
    def text(self) -> str:
        return self._node.get_text("", False)

    @property
    def string(self) -> Optional[str]:
        """
        Return the navigable string if this element contains exactly one text
        child (recursing through single-child elements), otherwise None.
        """
        return self._node.single_string()

    @string.setter
    def string(self, value: str) -> None:
        raise NotImplementedError(
            "xhtml v0.x: in-place tree modification is not yet supported."
        )

    @property
    def strings(self) -> Iterator[str]:
        yield from self._iter_strings()

    @property
    def stripped_strings(self) -> Iterator[str]:
        for s in self.strings:
            stripped = s.strip()
            if stripped:
                yield stripped

    def _iter_strings(self) -> Iterator[str]:
        for child in self._node.children():
            if child.is_tag():
                tag = Tag(child)
                yield from tag._iter_strings()
            else:
                txt = child.text_content()
                if txt:
                    yield txt

    # ── Search ────────────────────────────────────────────────────────────────

    def find(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        text: Any = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        """Return the first matching tag, or None."""
        attrs = dict(attrs or {})
        class_regex, id_regex, attrs, kwargs = _pop_regex_filters(attrs, kwargs)

        # Callable filter — iterate descendants in Python
        if callable(name) and not isinstance(name, type):
            for tag in self.descendants:
                if isinstance(tag, Tag) and name(tag):
                    if text is None or _text_matches(tag, text):
                        if not class_regex or class_regex.search(tag._node.get_attr("class") or ""):
                            if not id_regex or id_regex.search(tag._node.get_attr("id") or ""):
                                return tag
            return None

        query = _normalize_query(name, attrs, kwargs, recursive)
        result = self._node.find(query)
        if result is None:
            return None
        tag = Tag(result)
        # Post-filter regex
        if class_regex and not class_regex.search(tag._node.get_attr("class") or ""):
            result = None
        if id_regex and not id_regex.search(tag._node.get_attr("id") or ""):
            result = None
        if result is None:
            # Regex didn't match first result; fall back to find_all + filter
            candidates = self.find_all(name, attrs, recursive=recursive, **kwargs)
            candidates = _apply_extra_filters(candidates, class_regex, id_regex)
            return candidates[0] if candidates else None
        if text is not None and not _text_matches(tag, text):
            return next(
                (
                    t
                    for t in self.find_all(name, attrs, recursive=recursive, **kwargs)
                    if _text_matches(t, text)
                ),
                None,
            )
        return tag

    def find_all(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        text: Any = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> List["Tag"]:
        """Return a list of all matching tags."""
        attrs = dict(attrs or {})
        class_regex, id_regex, attrs, kwargs = _pop_regex_filters(attrs, kwargs)

        # Callable filter
        if callable(name) and not isinstance(name, type):
            results: List[Tag] = []
            for tag in self.descendants:
                if isinstance(tag, Tag) and name(tag):
                    if text is None or _text_matches(tag, text):
                        if not class_regex or class_regex.search(tag._node.get_attr("class") or ""):
                            if not id_regex or id_regex.search(tag._node.get_attr("id") or ""):
                                results.append(tag)
                                if limit and len(results) >= limit:
                                    break
            return results

        query = _normalize_query(name, attrs, kwargs, recursive)
        has_post = bool(text is not None or class_regex or id_regex)
        rust_limit = 0 if has_post else limit
        raw = self._node.find_all(query, rust_limit)
        results_list = [Tag(r) for r in raw]

        # Post-filter regex attrs
        results_list = _post_filter_attrs(results_list, attrs, kwargs)
        results_list = _apply_extra_filters(results_list, class_regex, id_regex)

        # Text filter
        if text is not None:
            results_list = [t for t in results_list if _text_matches(t, text)]

        if limit:
            results_list = results_list[:limit]
        return results_list

    # aliases
    findAll = find_all
    findNext = find

    def find_parent(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        parent = self.parent
        while parent is not None:
            if name is None or parent.name == name:
                return parent
            parent = parent.parent
        return None

    def find_parents(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> List["Tag"]:
        results: List[Tag] = []
        parent = self.parent
        while parent is not None:
            if name is None or parent.name == name:
                results.append(parent)
                if limit and len(results) >= limit:
                    break
            parent = parent.parent
        return results

    def find_next_sibling(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        for sib in self.next_siblings:
            if isinstance(sib, Tag):
                if name is None or sib.name == name:
                    return sib
        return None

    def find_next_siblings(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> List["Tag"]:
        results: List[Tag] = []
        for sib in self.next_siblings:
            if isinstance(sib, Tag):
                if name is None or sib.name == name:
                    results.append(sib)
                    if limit and len(results) >= limit:
                        break
        return results

    # ── CSS selectors ─────────────────────────────────────────────────────────

    def select(self, selector: str) -> List["Tag"]:
        """Return all elements matching a CSS selector."""
        return [Tag(r) for r in self._node.select(selector)]

    def select_one(self, selector: str) -> Optional["Tag"]:
        """Return the first element matching a CSS selector, or None."""
        result = self._node.select_one(selector)
        return Tag(result) if result is not None else None

    # ── Tree navigation ───────────────────────────────────────────────────────

    @property
    def parent(self) -> Optional["Tag"]:
        p = self._node.parent()
        return Tag(p) if p is not None else None

    @property
    def children(self) -> Iterator[Union["Tag", NavigableString]]:
        for child in self._node.children():
            if child.is_tag():
                yield Tag(child)
            else:
                txt = child.text_content()
                if txt:
                    yield NavigableString(rust_node=child)

    @property
    def contents(self) -> List[Union["Tag", NavigableString]]:
        return list(self.children)

    @property
    def descendants(self) -> Iterator[Union["Tag", NavigableString]]:
        for child in self.children:
            yield child
            if isinstance(child, Tag):
                yield from child.descendants

    @property
    def next_sibling(self) -> Optional[Union["Tag", NavigableString]]:
        sib = self._node.next_sibling()
        if sib is None:
            return None
        return Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    @property
    def previous_sibling(self) -> Optional[Union["Tag", NavigableString]]:
        sib = self._node.prev_sibling()
        if sib is None:
            return None
        return Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    @property
    def next_siblings(self) -> Iterator[Union["Tag", NavigableString]]:
        for sib in self._node.next_siblings():
            yield Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    @property
    def previous_siblings(self) -> Iterator[Union["Tag", NavigableString]]:
        for sib in self._node.prev_siblings():
            yield Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        return self._node.to_html()

    def __repr__(self) -> str:
        return self._node.to_html()

    def encode(self, encoding: str = "utf-8") -> bytes:
        return str(self).encode(encoding)

    def decode(self, formatter: Any = None) -> str:
        return str(self)

    def prettify(self, encoding: Optional[str] = None, formatter: Any = None) -> str:
        """Return a prettified version of the HTML (basic indentation)."""
        return _prettify(str(self))

    def decode_contents(self, indent_level: Any = None, formatter: Any = None) -> str:
        return self._node.inner_html()

    def encode_contents(
        self, indent_level: Any = None, encoding: str = "utf-8", formatter: Any = None
    ) -> bytes:
        return self.decode_contents().encode(encoding)

    # ── Misc ──────────────────────────────────────────────────────────────────

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return item in self.get_text()
        return False

    def __iter__(self) -> Iterator[Union["Tag", NavigableString]]:
        return self.children

    def __len__(self) -> int:
        return len(self.contents)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Tag):
            return str(self) == str(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))

    def __bool__(self) -> bool:
        return True


# ─── Xhtml ────────────────────────────────────────────────────────────────

class Xhtml(Tag):
    """
    Entry point for parsing an HTML or XML document.

    Usage
    -----
    from xhtml import Xhtml

    soup = Xhtml(html, "html.parser")
    soup.find("h1", class_="title").get_text()
    """

    _SUPPORTED_PARSERS = frozenset(
        {
            "html.parser",
            "html5lib",
            "lxml",
            "lxml-html",
            "lxml-xml",
            "html",
            "html5",
        }
    )

    def __init__(
        self,
        markup: Union[str, bytes] = "",
        features: Optional[Union[str, List[str]]] = "html.parser",
        **kwargs: Any,
    ) -> None:
        if isinstance(markup, bytes):
            try:
                markup = markup.decode("utf-8")
            except UnicodeDecodeError:
                markup = markup.decode("latin-1", errors="replace")

        # All parsers map to the same html5ever-based Rust parser
        self._rust_doc = RustDocument(markup)
        root = self._rust_doc.root_node()
        super().__init__(root)

    # Override name for the document root
    @property
    def name(self) -> str:  # type: ignore[override]
        return "[document]"

    # Override get_text / select / find to use document-level Rust methods
    def get_text(self, separator: str = "", strip: bool = False) -> str:
        return self._rust_doc.get_text(separator, strip)

    def select(self, selector: str) -> List[Tag]:
        return [Tag(r) for r in self._rust_doc.select(selector)]

    def select_one(self, selector: str) -> Optional[Tag]:
        result = self._rust_doc.select_one(selector)
        return Tag(result) if result is not None else None

    def find(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        text: Any = None,
        **kwargs: Any,
    ) -> Optional[Tag]:
        attrs = dict(attrs or {})
        class_regex, id_regex, attrs, kwargs = _pop_regex_filters(attrs, kwargs)

        if callable(name) and not isinstance(name, type):
            for tag in self.descendants:
                if isinstance(tag, Tag) and name(tag):
                    if not class_regex or class_regex.search(tag._node.get_attr("class") or ""):
                        if not id_regex or id_regex.search(tag._node.get_attr("id") or ""):
                            return tag
            return None

        query = _normalize_query(name, attrs, kwargs, recursive)
        result = self._rust_doc.find(query)
        if result is None:
            return None
        tag = Tag(result)
        if class_regex and not class_regex.search(tag._node.get_attr("class") or ""):
            result = None
        if id_regex and not id_regex.search(tag._node.get_attr("id") or ""):
            result = None
        if result is None:
            candidates = self.find_all(name, attrs, recursive=recursive, **kwargs)
            candidates = _apply_extra_filters(candidates, class_regex, id_regex)
            return candidates[0] if candidates else None
        if text is not None and not _text_matches(tag, text):
            return next(
                (
                    t
                    for t in self.find_all(name, attrs, recursive=recursive, **kwargs)
                    if _text_matches(t, text)
                ),
                None,
            )
        return tag

    def find_all(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        text: Any = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> List[Tag]:
        attrs = dict(attrs or {})
        class_regex, id_regex, attrs, kwargs = _pop_regex_filters(attrs, kwargs)

        if callable(name) and not isinstance(name, type):
            results: List[Tag] = []
            for tag in self.descendants:
                if isinstance(tag, Tag) and name(tag):
                    if text is None or _text_matches(tag, text):
                        if not class_regex or class_regex.search(tag._node.get_attr("class") or ""):
                            if not id_regex or id_regex.search(tag._node.get_attr("id") or ""):
                                results.append(tag)
                                if limit and len(results) >= limit:
                                    break
            return results

        query = _normalize_query(name, attrs, kwargs, recursive)
        has_post = bool(text is not None or class_regex or id_regex)
        rust_limit = 0 if has_post else limit
        raw = self._rust_doc.find_all(query, rust_limit)
        results_list = [Tag(r) for r in raw]
        results_list = _post_filter_attrs(results_list, attrs, kwargs)
        results_list = _apply_extra_filters(results_list, class_regex, id_regex)
        if text is not None:
            results_list = [t for t in results_list if _text_matches(t, text)]
        if limit:
            results_list = results_list[:limit]
        return results_list

    findAll = find_all

    def __repr__(self) -> str:
        return "<xhtml.Xhtml>"

    def __str__(self) -> str:
        return self._rust_doc.to_html()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _text_matches(tag: Tag, pattern: Any) -> bool:
    text = tag.get_text()
    if isinstance(pattern, str):
        return text == pattern
    if hasattr(pattern, "search"):
        return bool(pattern.search(text))
    return str(pattern) == text


def _post_filter_attrs(
    tags: List[Tag],
    attrs: Dict[str, Any],
    kwargs: Dict[str, Any],
) -> List[Tag]:
    """Apply regex / False attribute post-filters that Rust can not handle."""
    regex_filters: Dict[str, Any] = {}
    false_filters: List[str] = []

    for d in (attrs, kwargs):
        for k, v in d.items():
            if k in ("class_", "class", "id"):
                continue
            if hasattr(v, "search"):
                regex_filters[k] = v
            elif v is False:
                false_filters.append(k)

    if not regex_filters and not false_filters:
        return tags

    filtered = []
    for tag in tags:
        ok = True
        for k, rx in regex_filters.items():
            val = tag._node.get_attr(k)
            if val is None or not rx.search(val):
                ok = False
                break
        if ok:
            for k in false_filters:
                if tag.has_attr(k):
                    ok = False
                    break
        if ok:
            filtered.append(tag)
    return filtered


def _prettify(html: str, indent: int = 2) -> str:
    """Very basic prettifier: add newlines around block-level tags."""
    # Simple indent using a stack — good enough for display purposes
    import re as _re

    result = []
    depth = 0
    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    token_re = _re.compile(r"(<[^>]+>|[^<]+)")
    for token in token_re.findall(html):
        token = token.strip()
        if not token:
            continue
        if token.startswith("</"):
            depth = max(0, depth - 1)
            result.append(" " * (depth * indent) + token)
        elif token.startswith("<") and not token.startswith("<!"):
            result.append(" " * (depth * indent) + token)
            tag_name = _re.match(r"<(\w+)", token)
            if tag_name and tag_name.group(1).lower() not in VOID_ELEMENTS:
                if not token.endswith("/>"):
                    depth += 1
        else:
            result.append(" " * (depth * indent) + token)
    return "\n".join(result) + "\n"
