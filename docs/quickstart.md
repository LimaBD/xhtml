# Quick Start

Get up and running with `xhtml` in five minutes.

---

## Installation

```bash
pip install xhtml
```

---

## 1. Parse an HTML document

```python
from xhtml import Xhtml

html = """
<html>
  <head><title>My Site</title></head>
  <body>
    <h1 class="title hero">Welcome</h1>
    <ul id="nav">
      <li><a href="/home">Home</a></li>
      <li><a href="/about" class="active">About</a></li>
    </ul>
    <p class="intro">A short introduction paragraph.</p>
    <footer><a href="/contact">Contact us</a></footer>
  </body>
</html>
"""

soup = Xhtml(html, "html.parser")
```

The parser name (`"html.parser"`, `"lxml"`, `"html5lib"`) is accepted for compatibility but all strings route to the same Rust engine underneath.

`Xhtml` also accepts `bytes` — encoding is detected automatically (UTF-8 with latin-1 fallback).

---

## 2. Find elements

### By tag name

```python
heading  = soup.find("h1")
all_divs = soup.find_all("div")
```

### By CSS class

```python
hero    = soup.find("h1", class_="hero")
intros  = soup.find_all("p", class_="intro")

# Multiple classes — element must have ALL of them
special = soup.find("h1", class_="title hero")
```

### By id

```python
nav = soup.find("ul", id="nav")
```

### By attribute

```python
# Any element with the attribute present
all_links_with_href = soup.find_all("a", href=True)

# Exact attribute value
about_link = soup.find("a", href="/about")

# Multiple attributes
btn = soup.find("input", type="submit", name="go")
```

### Multiple tag names at once

```python
headings = soup.find_all(["h1", "h2", "h3"])
```

### CSS selectors

```python
active     = soup.select_one("ul#nav a.active")
all_links  = soup.select("ul a")
first_row  = soup.select_one("table tbody tr:first-child")
data_items = soup.select("li[data-n]")
```

### Regex filters

```python
import re

# Regex on class
articles = soup.find_all("article", class_=re.compile("featured"))

# Regex on attribute
https    = soup.find_all("a", href=re.compile(r"^https://"))

# Regex on id
targeted = soup.find_all(id=re.compile(r"^section-\d+$"))
```

### Callable / lambda

```python
# Full control: any callable that takes a Tag and returns bool
big_headings = soup.find_all(
    lambda tag: tag.name in ("h1", "h2") and len(tag.get_text()) > 50
)

# Find links that have both href and a class
rich_links = soup.find_all(
    lambda tag: tag.name == "a"
    and tag.has_attr("href")
    and tag.has_attr("class")
)
```

---

## 3. Read text and attributes

```python
tag = soup.find("h1", class_="hero")

# Text content
tag.get_text()              # "Welcome"
tag.get_text(strip=True)    # "Welcome" (strips surrounding whitespace)
tag.get_text(" | ")         # joined with separator
tag.text                    # alias for get_text()
tag.string                  # text if exactly one text child, else None

# Iterate text nodes
list(tag.strings)           # ["Welcome"]
list(tag.stripped_strings)  # same, with whitespace stripped, empty nodes skipped

# Attribute access
tag["class"]                # ['title', 'hero']  (class always returns list)
tag["href"]                 # raises KeyError if absent
tag.get("href")             # None if absent
tag.get("href", "#")        # custom default
tag.has_attr("class")       # True
tag.attrs                   # full dict
```

---

## 4. Navigate the tree

```python
heading = soup.find("h1")

# Parent
heading.parent              # <body> Tag
heading.find_parent("div")  # walk up until finding a <div>

# Children
list(heading.children)      # immediate children (Tags + NavigableStrings)
heading.contents            # same as list (direct children list)

# Descendants
for node in heading.descendants:
    print(node)

# Siblings
heading.next_sibling        # next node (may be whitespace NavigableString)
heading.previous_sibling

list(heading.next_siblings)
list(heading.previous_siblings)

heading.find_next_sibling("p")      # next sibling matching name/attrs
heading.find_next_siblings("p")     # all matching next siblings
```

---

## 5. Structured extraction with Pydantic

Instead of writing manual scraping logic, declare a model:

```python
from xhtml.extract import HtmlModel, Field
from typing import List

class Article(HtmlModel):
    title:   str       = Field(selector="h1.post-title")
    url:     str       = Field(selector="a.read-more", attr="href", default="#")
    summary: str       = Field(selector="p.intro",     strip=True, default="")
    tags:    List[str] = Field(selector=".tag",         multiple=True, default_factory=list)

# Parse a single article
article = Article.from_html(html)
print(article.title)
print(article.tags)

# Parse a listing page — one model per matching element
articles = Article.from_html_list(page_html, item_selector="article.post")
```

See [Structured Extraction](extraction.md) for the full guide.

---

## 6. Render and encode

```python
tag = soup.find("div", id="main")

str(tag)                  # outer HTML string
tag.encode("utf-8")       # outer HTML as bytes
tag.decode_contents()     # inner HTML (children only)
tag.prettify()            # indented HTML string
```

---

## Next steps

- [API Reference](api-reference.md) — every method, parameter, and return type
- [Structured Extraction](extraction.md) — typed models, transforms, bulk extraction
- [Migration Guide](migration.md) — switching from BeautifulSoup or lxml
