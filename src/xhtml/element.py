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


# ─── ResultSet ───────────────────────────────────────────────────────────────

class ResultSet(list):
    """
    A list subclass returned by find_all() / find_all_next() / etc.
    Mirrors BeautifulSoup4's ResultSet — carries a reference to the
    originating tag via the `source` attribute.
    """

    def __init__(self, source: Any, result: Iterable = ()):
        super().__init__(result)
        self.source = source

    def __repr__(self) -> str:  # type: ignore[override]
        return f"[{', '.join(repr(i) for i in self)}]"


# ─── HTML void/empty elements ────────────────────────────────────────────────

_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


# ─── Pure-Python tag filter ──────────────────────────────────────────────────

def _matches_filter(
    node: Any,
    name: Any,
    attrs: Optional[Dict[str, Any]],
    kwargs: Optional[Dict[str, Any]],
) -> bool:
    """
    Pure-Python tag matcher — used for find_next / find_previous and
    other navigation helpers that operate on pre-fetched Python Tag objects.
    Accepts the same argument shapes as find() / find_all().
    """
    if not isinstance(node, Tag):
        return False

    attrs = dict(attrs or {})
    kwargs = dict(kwargs or {})

    # --- tag name ---
    if name is not None and name is not True:
        if isinstance(name, str):
            if node.name != name:
                return False
        elif isinstance(name, (list, tuple)):
            if node.name not in name:
                return False
        elif callable(name) and not isinstance(name, type):
            if not name(node):
                return False
        elif hasattr(name, "search"):  # compiled regex
            if not name.search(node.name):
                return False

    # --- merge attrs + kwargs, handle class_ alias ---
    all_attrs: Dict[str, Any] = {**attrs, **kwargs}
    class_val = all_attrs.pop("class_", all_attrs.pop("class", None))
    id_val = all_attrs.pop("id", None)

    # --- id ---
    if id_val is not None and id_val is not True:
        if hasattr(id_val, "search"):
            if not id_val.search(node.get("id", "") or ""):
                return False
        else:
            if node.get("id") != str(id_val):
                return False
    elif id_val is True:
        if not node.has_attr("id"):
            return False

    # --- class ---
    if class_val is not None and class_val is not True:
        tag_classes: List[str] = node.get("class") or []
        if hasattr(class_val, "search"):
            cls_str = " ".join(tag_classes)
            if not class_val.search(cls_str):
                return False
        elif isinstance(class_val, str):
            required = class_val.split()
            if not all(c in tag_classes for c in required):
                return False
        elif isinstance(class_val, (list, tuple)):
            if not all(c in tag_classes for c in class_val):
                return False
    elif class_val is True:
        if not node.has_attr("class"):
            return False

    # --- other attributes ---
    for k, v in all_attrs.items():
        if v is True:
            if not node.has_attr(k):
                return False
        elif v is False or v is None:
            if node.has_attr(k):
                return False
        elif hasattr(v, "search"):
            attr_val = node.get(k)
            if attr_val is None or not v.search(str(attr_val)):
                return False
        elif isinstance(v, str):
            if node.get(k) != v:
                return False
        elif isinstance(v, (list, tuple)):
            if node.get(k) not in [str(x) for x in v]:
                return False
        else:
            if node.get(k) != str(v):
                return False

    return True


# ─── Node wrapping / query helpers ──────────────────────────────────────────

def _wrap_node(rust_node: RustNode) -> Any:
    """Wrap a RustNode in the appropriate Python class."""
    return Tag(rust_node) if rust_node.is_tag() else NavigableString(rust_node=rust_node)


def _is_simple_query(
    name: Any,
    attrs: Optional[Dict[str, Any]],
    kwargs: Optional[Dict[str, Any]],
) -> bool:
    """
    Return True when the query contains no callable or regex values — the Rust
    engine can execute it entirely without Python post-filtering.
    """
    if name is not None and name is not True:
        if callable(name) and not isinstance(name, type):
            return False
        if hasattr(name, "search"):
            return False
    for v in list((attrs or {}).values()) + list((kwargs or {}).values()):
        if hasattr(v, "search") or (callable(v) and not isinstance(v, type)):
            return False
    return True


# ─── Mutation stub message ───────────────────────────────────────────────────

_MUTATION_MSG = (
    "xhtml v0.x: in-place tree modification is not yet supported. "
    "The Rust core uses a read-optimised immutable tree. "
    "Tree mutation support is planned for a future version."
)


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

    # ── BS4-parity: NavigableString has name=None ─────────────────────────────

    @property
    def name(self) -> None:  # type: ignore[override]
        return None

    @property
    def hidden(self) -> bool:
        return False

    # ── Text ──────────────────────────────────────────────────────────────────

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        text = str(self)
        return text.strip() if strip else text

    # aliases
    getText = get_text

    @property
    def text(self) -> str:
        return str(self)

    @property
    def string(self) -> "NavigableString":
        return self

    @property
    def strings(self) -> Iterator[str]:
        yield str(self)

    @property
    def stripped_strings(self) -> Iterator[str]:
        s = str(self).strip()
        if s:
            yield s

    # ── Sibling iterators ─────────────────────────────────────────────────────

    @property
    def next_siblings(self) -> Iterator[Any]:
        if self._node:
            for sib in self._node.next_siblings():
                yield Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    @property
    def previous_siblings(self) -> Iterator[Any]:
        if self._node:
            for sib in self._node.prev_siblings():
                yield Tag(sib) if sib.is_tag() else NavigableString(rust_node=sib)

    # ── Document-order navigation ─────────────────────────────────────────────

    @property
    def next_element(self) -> Optional[Any]:
        if not self._node:
            return None
        n = self._node.next_element_node()
        return _wrap_node(n) if n is not None else None

    @property
    def previous_element(self) -> Optional[Any]:
        if not self._node:
            return None
        n = self._node.previous_element_node()
        return _wrap_node(n) if n is not None else None

    @property
    def next_elements(self) -> Iterator[Any]:
        nxt: Any = self.next_element
        while nxt is not None:
            yield nxt
            nxt = nxt.next_element

    @property
    def previous_elements(self) -> Iterator[Any]:
        prev: Any = self.previous_element
        while prev is not None:
            yield prev
            prev = prev.previous_element

    # ── Parent navigation ─────────────────────────────────────────────────────

    @property
    def parents(self) -> Iterator["Tag"]:
        if self._node:
            for n in self._node.ancestors_list():
                yield Tag(n)

    def find_parent(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_ancestors_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for par in self.parents:
            if _matches_filter(par, name, attrs, kwargs):
                return par
        return None

    def find_parents(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_ancestors_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for par in self.parents:
            if _matches_filter(par, name, attrs, kwargs):
                results.append(par)
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    # ── Forward/backward document-order search ────────────────────────────────

    def find_next(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_nodes(q, 1)
            return Tag(nodes[0]) if nodes else None
        for el in self.next_elements:
            if _matches_filter(el, name, attrs, kwargs):
                return el  # type: ignore[return-value]
        return None

    def find_all_next(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_nodes(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for el in self.next_elements:
            if _matches_filter(el, name, attrs, kwargs):
                results.append(el)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    def find_previous(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_previous_nodes(q, 1)
            return Tag(nodes[0]) if nodes else None
        for el in self.previous_elements:
            if _matches_filter(el, name, attrs, kwargs):
                return el  # type: ignore[return-value]
        return None

    def find_all_previous(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_previous_nodes(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for el in self.previous_elements:
            if _matches_filter(el, name, attrs, kwargs):
                results.append(el)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    # ── Sibling search ────────────────────────────────────────────────────────

    def find_next_sibling(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_siblings_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for sib in self.next_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                return sib  # type: ignore[return-value]
        return None

    def find_next_siblings(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_siblings_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for sib in self.next_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                results.append(sib)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    def find_previous_sibling(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_prev_siblings_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for sib in self.previous_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                return sib  # type: ignore[return-value]
        return None

    def find_previous_siblings(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if self._node and _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_prev_siblings_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for sib in self.previous_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                results.append(sib)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    # ── Aliases (BS4 camelCase) ───────────────────────────────────────────────
    findNext = find_next
    findAllNext = find_all_next
    findPrevious = find_previous
    findAllPrevious = find_all_previous
    findNextSibling = find_next_sibling
    findNextSiblings = find_next_siblings
    findPreviousSibling = find_previous_sibling
    findPreviousSiblings = find_previous_siblings
    findParent = find_parent
    findParents = find_parents

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
    ) -> "ResultSet":
        """Return a ResultSet of all matching tags."""
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
            return ResultSet(self, results)

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
        return ResultSet(self, results_list)

    # aliases
    findAll = find_all

    def find_parent(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_ancestors_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for par in self.parents:
            if _matches_filter(par, name, attrs, kwargs):
                return par
        return None

    def find_parents(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_ancestors_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for par in self.parents:
            if _matches_filter(par, name, attrs, kwargs):
                results.append(par)
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    # BS4 camelCase aliases for parent navigation
    findParent = find_parent
    findParents = find_parents

    def find_next_sibling(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_siblings_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for sib in self.next_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                return sib  # type: ignore[return-value]
        return None

    def find_next_siblings(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_siblings_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for sib in self.next_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                results.append(sib)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    def find_previous_sibling(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_prev_siblings_q(q, 1)
            return Tag(nodes[0]) if nodes else None
        for sib in self.previous_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                return sib  # type: ignore[return-value]
        return None

    def find_previous_siblings(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_prev_siblings_q(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for sib in self.previous_siblings:
            if _matches_filter(sib, name, attrs, kwargs):
                results.append(sib)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    def find_next(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        """Find the first element following this tag in document order."""
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_nodes(q, 1)
            return Tag(nodes[0]) if nodes else None
        for el in self.next_elements:
            if _matches_filter(el, name, attrs, kwargs):
                return el  # type: ignore[return-value]
        return None

    def find_all_next(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        """Find all elements following this tag in document order."""
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_next_nodes(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for el in self.next_elements:
            if _matches_filter(el, name, attrs, kwargs):
                results.append(el)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    def find_previous(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional["Tag"]:
        """Find the first element before this tag in document order."""
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_previous_nodes(q, 1)
            return Tag(nodes[0]) if nodes else None
        for el in self.previous_elements:
            if _matches_filter(el, name, attrs, kwargs):
                return el  # type: ignore[return-value]
        return None

    def find_all_previous(
        self,
        name: Any = None,
        attrs: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        **kwargs: Any,
    ) -> "ResultSet":
        """Find all elements before this tag in document order."""
        if _is_simple_query(name, attrs, kwargs):
            q = _normalize_query(name, dict(attrs or {}), kwargs)
            nodes = self._node.find_previous_nodes(q, limit)
            return ResultSet(self, [Tag(n) for n in nodes])
        results: List[Tag] = []
        for el in self.previous_elements:
            if _matches_filter(el, name, attrs, kwargs):
                results.append(el)  # type: ignore[arg-type]
                if limit and len(results) >= limit:
                    break
        return ResultSet(self, results)

    # BS4 camelCase aliases
    findNext = find_next
    findAllNext = find_all_next
    findPrevious = find_previous
    findAllPrevious = find_all_previous
    findNextSibling = find_next_sibling
    findNextSiblings = find_next_siblings
    findPreviousSibling = find_previous_sibling
    findPreviousSiblings = find_previous_siblings

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
    def parents(self) -> Iterator["Tag"]:
        """Iterator yielding each ancestor from immediate parent to document root."""
        for n in self._node.ancestors_list():
            yield Tag(n)

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
        for n in self._node.all_descendants():
            if n.is_tag():
                yield Tag(n)
            else:
                txt = n.text_content()
                if txt:
                    yield NavigableString(rust_node=n)

    @property
    def self_and_descendants(self) -> Iterator[Union["Tag", NavigableString]]:
        """Yield self, then all descendants (same as BS4)."""
        yield self
        yield from self.descendants

    @property
    def self_and_parents(self) -> Iterator["Tag"]:
        """Yield self, then all parent tags."""
        yield self
        yield from self.parents

    @property
    def self_and_next_siblings(self) -> Iterator[Union["Tag", NavigableString]]:
        """Yield self, then all following siblings."""
        yield self
        yield from self.next_siblings

    @property
    def self_and_previous_siblings(self) -> Iterator[Union["Tag", NavigableString]]:
        """Yield self, then all preceding siblings."""
        yield self
        yield from self.previous_siblings

    @property
    def self_and_next_elements(self) -> Iterator[Any]:
        """Yield self, then all following elements in document order."""
        yield self
        yield from self.next_elements

    @property
    def self_and_previous_elements(self) -> Iterator[Any]:
        """Yield self, then all preceding elements in document order."""
        yield self
        yield from self.previous_elements

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

    @property
    def next_element(self) -> Optional[Union["Tag", NavigableString]]:
        n = self._node.next_element_node()
        return _wrap_node(n) if n is not None else None

    @property
    def previous_element(self) -> Optional[Union["Tag", NavigableString]]:
        n = self._node.previous_element_node()
        return _wrap_node(n) if n is not None else None

    @property
    def next_elements(self) -> Iterator[Any]:
        """Iterate over all nodes following this tag in document order."""
        nxt: Any = self.next_element
        while nxt is not None:
            yield nxt
            nxt = nxt.next_element

    @property
    def previous_elements(self) -> Iterator[Any]:
        """Iterate over all nodes preceding this tag in document order."""
        prev: Any = self.previous_element
        while prev is not None:
            yield prev
            prev = prev.previous_element

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

    # ── Utility ───────────────────────────────────────────────────────────────

    @property
    def hidden(self) -> bool:
        """False for regular tags; overridden to True in Xhtml (document root)."""
        return False

    @property
    def is_empty_element(self) -> bool:
        """True if this is an HTML void element (br, img, hr, input, …)."""
        return self.name.lower() in _VOID_ELEMENTS

    # BS4 alias
    isSelfClosing = is_empty_element

    def get_attribute_list(self, key: str, default: Any = None) -> List[Any]:
        """
        Return the value of `key` as a list.
        • class → list of class tokens
        • Any other attribute → [value]   (or [None] if absent)
        Mirrors BS4's Tag.get_attribute_list().
        """
        val = self.get(key, default)
        if val is None:
            return [None]
        if isinstance(val, list):
            return val
        return [val]

    def has_key(self, key: str) -> bool:
        """Deprecated BS4 alias for has_attr()."""
        return self.has_attr(key)

    def getText(self, separator: str = "", strip: bool = False) -> str:
        """BS4 alias for get_text()."""
        return self.get_text(separator, strip)

    def index(self, element: Any) -> int:
        """
        Return the index of `element` within this tag's .contents list.
        Raises ValueError if the element is not a direct child.
        """
        for i, child in enumerate(self.contents):
            if child == element:
                return i
        raise ValueError(f"{element!r} is not in the contents of {self!r}")

    # ── Tree modification stubs (not yet supported) ────────────────────────────

    def append(self, tag: Any) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def extend(self, tags: Iterable[Any]) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def insert(self, position: int, new_child: Any) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def insert_before(self, *args: Any) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def insert_after(self, *args: Any) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def clear(self) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def extract(self) -> "Tag":
        raise NotImplementedError(_MUTATION_MSG)

    def decompose(self) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    def replace_with(self, *args: Any) -> "Tag":
        raise NotImplementedError(_MUTATION_MSG)

    def replace_with_children(self) -> "Tag":
        raise NotImplementedError(_MUTATION_MSG)

    def unwrap(self) -> "Tag":
        raise NotImplementedError(_MUTATION_MSG)

    def wrap(self, wrap_inside: Any) -> "Tag":
        raise NotImplementedError(_MUTATION_MSG)

    def smooth(self) -> None:
        raise NotImplementedError(_MUTATION_MSG)

    # BS4 camelCase mutation aliases
    replaceWith = replace_with
    replaceWithChildren = replace_with_children

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

    def __call__(self, *args: Any, **kwargs: Any) -> "ResultSet":
        """Shortcut: tag(...) is equivalent to tag.find_all(...)."""
        return self.find_all(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """
        BS4-compatible attribute access:
        ``tag.div`` returns ``tag.find("div")``, or None if not found.
        Dunder attributes raise AttributeError normally.
        """
        if name.startswith("__"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        # Delegate to find() — returns None when the tag isn't present
        return self.find(name)




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
        return ResultSet(self, results_list)

    findAll = find_all

    # The document root is "hidden" (not rendered as a tag itself)
    @property
    def hidden(self) -> bool:  # type: ignore[override]
        return True

    # getText alias — needs explicit override so it targets Rust get_text
    def getText(self, separator: str = "", strip: bool = False) -> str:  # type: ignore[override]
        return self.get_text(separator, strip)

    def __repr__(self) -> str:
        return "<xhtml.Xhtml>"

    def __str__(self) -> str:
        return self._rust_doc.to_html()

    def __getattr__(self, name: str) -> Any:
        """BS4-compatible: document.title → document.find('title'), etc."""
        if name.startswith("__"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        return self.find(name)


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
