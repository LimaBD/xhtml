# Migration Guide

Switching to `xhtml` from another HTML parser is designed to be nearly effortless. In most projects, **only the import line changes**.

---

## From BeautifulSoup (bs4)

```python
# Before
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, "html.parser")

# After
from xhtml import Xhtml
soup = Xhtml(html, "html.parser")
```

That is all. The rest of your code — every `find`, `find_all`, CSS selector, attribute access, tree navigation method — is designed to behave identically.

### Verification

Run your existing test suite. If you have tests that validate scraping outputs, they should pass without modification.

If you use the `BS4_MODE=1` compatibility flag from xhtml's own test suite as inspiration, you can write dual-mode tests:

```python
import os
if os.environ.get("BS4_MODE") == "1":
    from bs4 import BeautifulSoup as Parser
else:
    from xhtml import Xhtml as Parser

soup = Parser(html, "html.parser")
```

---

## From lxml

lxml exposes an ElementTree-style API that is significantly different from BeautifulSoup's interface. Migration requires adapting the query style.

### Parsing

```python
# lxml
from lxml import html as lhtml
tree = lhtml.fromstring(markup)

# xhtml
from xhtml import Xhtml
soup = Xhtml(markup, "html.parser")
```

### XPath → CSS selectors

```python
# lxml XPath
tree.xpath("//div[@class='content']//a/@href")

# xhtml CSS selector
[a["href"] for a in soup.select("div.content a")]
```

### Attribute access

```python
# lxml
el.get("href")
el.attrib

# xhtml
el.get("href")
el.attrs
```

---

## From selectolax

```python
# selectolax
from selectolax.parser import HTMLParser
tree = HTMLParser(html)
node = tree.css_first("h1")
text = node.text()

# xhtml
from xhtml import Xhtml
soup = Xhtml(html)
node = soup.select_one("h1")
text = node.get_text()
```

---

## Parser name compatibility

xhtml accepts all well-known parser strings — they all route to the same Rust engine:

| String passed      | Engine used |
| ------------------ | ----------- |
| `"html.parser"`    | Rust (html5ever) |
| `"lxml"`           | Rust (html5ever) |
| `"html5lib"`       | Rust (html5ever) |
| `"lxml-html"`      | Rust (html5ever) |
| `"lxml-xml"`       | Rust (html5ever) |
| `"html"`           | Rust (html5ever) |
| `"html5"`          | Rust (html5ever) |
| `None`             | Rust (html5ever) |

---

## Feature parity reference

### Fully supported

| Feature | Notes |
| ------- | ----- |
| `find(name, attrs, recursive, text, **kwargs)` | All filter types supported |
| `find_all(name, attrs, recursive, text, limit, **kwargs)` | All filter types supported |
| `select(css_selector)` | Full CSS3 selector support |
| `select_one(css_selector)` | — |
| String, list, and regex filters for `name` | — |
| `class_` kwarg (list or string) | — |
| `id` kwarg | — |
| Arbitrary attribute filters (`href=`, `type=`, etc.) | Exact value, `True`, or regex |
| `get_text(separator, strip)` | — |
| `text`, `string`, `strings`, `stripped_strings` | — |
| `tag[key]`, `tag.get(key)`, `tag.has_attr(key)`, `tag.attrs` | `class` always returned as list |
| `parent`, `children`, `contents`, `descendants` | — |
| `next_sibling`, `previous_sibling`, `next_siblings`, `previous_siblings` | — |
| `find_parent`, `find_parents` | — |
| `find_next_sibling`, `find_next_siblings` | — |
| `str(tag)`, `tag.encode()`, `tag.decode_contents()`, `tag.prettify()` | — |
| Callable / lambda filters | — |
| `NavigableString` | Inherits `str` |
| `Xhtml(bytes)` | UTF-8 / latin-1 auto-detection |

### Planned (v0.2)

| Feature | Workaround today |
| ------- | ---------------- |
| `tag.decompose()` | Reconstruct from search results in Python |
| `tag.insert(position, new_tag)` | Build the HTML string manually |
| `tag.replace_with(new_tag)` | Post-process in Python |
| `SoupStrainer` | Use `find_all(limit=)` to reduce work |
| `prettify()` with custom indent rules | Use `str(tag)` + a formatting library |
| Callable `formatter` in `encode()` | Post-process the string in Python |

---

## Common patterns after migration

### Getting all links

```python
# Before (bs4)
links = [a["href"] for a in soup.find_all("a", href=True)]

# After (xhtml) — same code, same result
links = [a["href"] for a in soup.find_all("a", href=True)]
```

### Structured extraction (new in xhtml)

If you were doing this in bs4:

```python
# BeautifulSoup (manual)
results = []
for card in soup.find_all("div", class_="product-card"):
    results.append({
        "name":  card.find("h2").get_text(strip=True),
        "price": card.find("span", class_="price").get_text(strip=True),
        "url":   card.find("a")["href"],
    })
```

xhtml lets you replace this with a typed model:

```python
from xhtml.extract import HtmlModel, Field

class Product(HtmlModel):
    name:  str = Field(selector="h2")
    price: str = Field(selector="span.price")
    url:   str = Field(selector="a", attr="href", default="#")

products = Product.from_html_list(html, item_selector=".product-card")
```

See [Structured Extraction](extraction.md) for the full guide.

---

## Need help?

If you encounter a behaviour difference from BeautifulSoup, please [open an issue](https://github.com/LimaBD/xhtml/issues) and include:

- The HTML you are parsing (or a minimal reproduction)
- The output you expected
- The output you got
- Your Python version and OS
