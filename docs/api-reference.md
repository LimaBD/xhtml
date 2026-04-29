# API Reference

Complete reference for `xhtml.Xhtml`, `xhtml.Tag`, and `xhtml.NavigableString`.

---

## `Xhtml`

The entry point for document parsing. Inherits all `Tag` methods.

```python
from xhtml import Xhtml

soup = Xhtml(markup, features="html.parser", **kwargs)
```

### Parameters

| Parameter  | Type                           | Default         | Description |
| ---------- | ------------------------------ | --------------- | ----------- |
| `markup`   | `str \| bytes`                 | `""`            | The HTML or XML source. Bytes are decoded as UTF-8 (fallback: latin-1). |
| `features` | `str \| List[str] \| None`     | `"html.parser"` | Parser name. Any value (`"html.parser"`, `"lxml"`, `"html5lib"`, etc.) routes to the Rust engine. |

### Properties

| Property | Type      | Description |
| -------- | --------- | ----------- |
| `name`   | `str`     | Always `"[document]"` |

### Methods

`Xhtml` exposes the same searching, navigation, and rendering methods as `Tag` (documented below), plus these document-level methods:

#### `find(name=None, attrs=None, recursive=True, text=None, **kwargs) → Tag | None`

Returns the first matching element in the document. See [`Tag.find`](#tagfind).

#### `find_all(name=None, attrs=None, recursive=True, text=None, limit=0, **kwargs) → List[Tag]`

Returns all matching elements. See [`Tag.find_all`](#tagfind_all).

#### `select(selector) → List[Tag]`

Runs a CSS selector against the document root.

```python
results = soup.select("article.post h2.title")
```

#### `select_one(selector) → Tag | None`

Returns the first CSS selector match, or `None`.

```python
link = soup.select_one("nav a.active")
```

#### `get_text(separator="", strip=False) → str`

Returns all text in the document concatenated.

```python
text = soup.get_text(" ", strip=True)
```

---

## `Tag`

Wraps a single HTML element node. All heavy operations are delegated to the Rust engine.

---

### Identity

#### `name` → `str`

The tag name (`"div"`, `"a"`, `"p"`, …).

```python
tag.name   # "div"
```

---

### Attribute access

#### `tag[key]` → `Any`

Returns the attribute value. Raises `KeyError` if the attribute is absent. The `class` attribute always returns a list.

```python
tag["href"]     # "/about"
tag["class"]    # ["card", "featured"]
```

#### `tag.get(key, default=None)` → `Any`

Returns the attribute value, or `default` if absent.

```python
tag.get("href", "#")
```

#### `tag.has_attr(key)` → `bool`

Returns `True` if the attribute exists, `False` otherwise.

```python
tag.has_attr("data-id")
```

#### `tag.attrs` → `Dict[str, Any]`

Returns a dictionary of all attributes. The `class` value is a list; all others are strings.

```python
tag.attrs   # {"class": ["card", "featured"], "href": "/about"}
```

---

### Text retrieval

#### `tag.get_text(separator="", strip=False)` → `str`

Concatenates all text content under this node.

- `separator` — inserted between each text node.
- `strip` — if `True`, strips leading and trailing whitespace from each text piece.

```python
tag.get_text()               # "Hello World"
tag.get_text(" ", strip=True)  # "Hello World"
```

#### `tag.text` → `str`

Alias for `get_text()` with no arguments.

#### `tag.string` → `str | None`

Returns the text content if the tag has exactly one text child; `None` otherwise.

```python
p = soup.find("p")
p.string   # "Hello" or None
```

#### `tag.strings` → `Iterator[str]`

Iterates over all text nodes inside the tag.

```python
list(tag.strings)          # ["Hello ", "World"]
```

#### `tag.stripped_strings` → `Iterator[str]`

Same as `strings`, but strips whitespace and skips empty strings.

```python
list(tag.stripped_strings)  # ["Hello", "World"]
```

---

### Finding elements

#### `tag.find(name=None, attrs=None, recursive=True, text=None, **kwargs)` → `Tag | None`

Returns the **first** matching descendant, or `None` if nothing matches.

**Parameters**

| Parameter   | Type                                    | Description |
| ----------- | --------------------------------------- | ----------- |
| `name`      | `str \| List[str] \| re.Pattern \| Callable \| None` | Tag name(s) to match. `None` matches any tag. |
| `attrs`     | `dict \| None`                          | Dictionary of attribute filters. |
| `recursive` | `bool`                                  | If `False`, searches only direct children. Default `True`. |
| `text`      | `str \| re.Pattern \| None`             | Filters by text content. |
| `**kwargs`  | —                                       | Shorthand for attribute filters (`class_`, `id`, `href`, etc.). |

**Examples**

```python
soup.find("p")
soup.find("p", class_="intro")
soup.find(id="main")
soup.find("a", href=True)                     # any <a> with href
soup.find("a", href="/about")                 # exact match
soup.find("a", href=re.compile(r"^https?://"))  # regex
soup.find(lambda tag: tag.name == "div" and tag.has_attr("data-id"))
soup.find("h2", text=re.compile("Breaking"))
```

#### `tag.find_all(name=None, attrs=None, recursive=True, text=None, limit=0, **kwargs)` → `List[Tag]`

Returns **all** matching descendants as a list.

Same parameters as `find`, plus:

| Parameter | Type  | Default | Description |
| --------- | ----- | ------- | ----------- |
| `limit`   | `int` | `0`     | Maximum number of results. `0` means no limit. |

```python
soup.find_all("a")
soup.find_all("a", limit=5)
soup.find_all(["h1", "h2", "h3"])
soup.find_all(class_="card")
soup.find_all("a", href=re.compile(r"^https?://"))
```

`findAll` is an alias for `find_all`.

#### `tag.select(selector)` → `List[Tag]`

Runs a CSS selector and returns all matches.

```python
tag.select("ul li a")
tag.select("div.container > p.intro")
tag.select("input[type='text']")
tag.select("li:nth-child(2)")
tag.select("li:first-child")
tag.select("[data-n]")         # any element with data-n attribute
```

#### `tag.select_one(selector)` → `Tag | None`

Returns the first CSS selector match, or `None`.

```python
tag.select_one("#main .title")
```

---

### Tree navigation

#### `tag.parent` → `Tag | None`

The immediate parent node.

#### `tag.children` → `Iterator[Tag | NavigableString]`

Iterates over direct children (skips empty text nodes).

#### `tag.contents` → `List[Tag | NavigableString]`

Direct children as a list.

#### `tag.descendants` → `Iterator[Tag | NavigableString]`

All descendants in depth-first order.

#### `tag.next_sibling` → `Tag | NavigableString | None`

The next sibling node.

#### `tag.previous_sibling` → `Tag | NavigableString | None`

The previous sibling node.

#### `tag.next_siblings` → `Iterator[Tag | NavigableString]`

All following siblings.

#### `tag.previous_siblings` → `Iterator[Tag | NavigableString]`

All preceding siblings (in reverse document order).

#### `tag.find_parent(name=None, attrs=None, **kwargs)` → `Tag | None`

Walks up the ancestor chain and returns the first matching ancestor.

```python
section = link.find_parent("section")
div     = link.find_parent("div", class_="container")
```

#### `tag.find_parents(name=None, attrs=None, limit=0, **kwargs)` → `List[Tag]`

Returns all matching ancestors.

#### `tag.find_next_sibling(name=None, attrs=None, **kwargs)` → `Tag | None`

Returns the first matching sibling after this node.

#### `tag.find_next_siblings(name=None, attrs=None, limit=0, **kwargs)` → `List[Tag]`

Returns all matching siblings after this node.

---

### Rendering

#### `str(tag)` → `str`

Returns the outer HTML of the element.

```python
str(soup.find("div", id="main"))
# '<div id="main"><h1>Hello</h1></div>'
```

#### `tag.encode(encoding="utf-8")` → `bytes`

Returns the outer HTML as bytes.

#### `tag.decode_contents()` → `str`

Returns the inner HTML (children only, excluding the outer tag itself).

```python
tag.decode_contents()
# '<h1>Hello</h1><p>World</p>'
```

#### `tag.encode_contents(encoding="utf-8")` → `bytes`

Inner HTML as bytes.

#### `tag.prettify()` → `str`

Returns indented HTML.

---

### Misc

#### `tag.__contains__(item)` → `bool`

Returns `True` if `item` appears in the tag's text content.

```python
"Hello" in tag   # True
```

#### `tag.__iter__()`

Iterates over `children`.

#### `tag.__len__()`

Number of direct children in `contents`.

#### `tag.__eq__(other)` → `bool`

Two tags are equal if their outer HTML strings match.

#### `tag.__bool__()`

Always `True` — a `Tag` is always truthy.

---

## `NavigableString`

A text node inside the tree. Inherits from `str`.

```python
p = soup.find("p")
for item in p.children:
    if isinstance(item, NavigableString):
        print(repr(item))   # 'Hello'
```

### Properties

| Property           | Type                          | Description |
| ------------------ | ----------------------------- | ----------- |
| `parent`           | `Tag \| None`                  | The parent element |
| `next_sibling`     | `Tag \| NavigableString \| None` | Next sibling |
| `previous_sibling` | `Tag \| NavigableString \| None` | Previous sibling |
| `text`             | `str`                         | The string value |

### Methods

#### `get_text(separator="", strip=False)` → `str`

Returns the string (respecting `strip`).

---

## Compatibility aliases

| Alias | Resolves to |
| ----- | ----------- |
| `Xhtml.findAll` | `Xhtml.find_all` |
| `Tag.findAll` | `Tag.find_all` |
| `Tag.findNext` | `Tag.find` |

### Compatibility imports

```python
from xhtml._compat import SoupStrainer      # None — not yet supported
from xhtml._compat import FeatureNotFound   # ImportError
from xhtml._compat import ParserRejectedMarkup  # ValueError
```
