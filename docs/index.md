# xhtml Documentation

> **Fast, ergonomic HTML/XML parsing for Python — powered by a Rust core.**

---

## Overview

`xhtml` is a Python library that replaces pure-Python HTML parsers with a Rust engine, delivering **~34× faster** parsing and querying while keeping the same familiar API you already use.

### Why it exists

AI agents, data pipelines, and scraping services routinely process thousands of pages. A standard Python parser takes ~37 seconds to process 1,000 × 100 KB pages. `xhtml` takes ~1.1 seconds.

That is not a 10% improvement. It is a **34× multiplier** on your pipeline's throughput — with zero migration cost.

### Key capabilities

| Capability | Description |
| --- | --- |
| **Familiar API** | Same `find`, `find_all`, CSS selectors, attribute access, and tree navigation you already know |
| **Rust engine** | `html5ever` tokeniser + arena tree + DFS query engine — all in Rust, zero GC overhead |
| **Pydantic extraction** | Declare typed models, extract structured data from HTML in one call |
| **Drop-in migration** | One import line change from BeautifulSoup |
| **No system dependencies** | Pre-compiled wheels for Linux, macOS, Windows — no Rust required |

---

## Installation

```bash
pip install xhtml
```

Pre-compiled wheels ship for:

- Linux x86\_64 / aarch64 (manylinux)
- macOS x86\_64 / arm64 (M1 / M2 / M3)
- Windows x86\_64

---

## Contents

```{toctree}
:maxdepth: 1
:caption: Getting Started

quickstart
```

```{toctree}
:maxdepth: 1
:caption: Reference

api-reference
extraction
migration
```

---

## Five-second example

```python
from xhtml import Xhtml

soup = Xhtml(html, "html.parser")

# familiar API
titles   = soup.find_all("h2", class_="post-title")
link     = soup.select_one("nav a.active")["href"]
summary  = soup.find("p", class_="intro").get_text(strip=True)

# structured extraction
from xhtml.extract import HtmlModel, Field
from typing import List

class Article(HtmlModel):
    title: str       = Field(selector="h1")
    tags:  List[str] = Field(selector=".tag", multiple=True, default_factory=list)

article  = Article.from_html(html)
articles = Article.from_html_list(page_html, item_selector="article.post")
```

---

## Architecture

```
    Your Python code
          │
          ▼
  xhtml Python API   ← clean, expressive
          │  PyO3 bindings
          ▼
   Rust engine (_core)
    ├─ html5ever         ← streaming, spec-compliant HTML5 parser
    ├─ arena tree        ← contiguous memory, zero GC pressure
    ├─ DFS query engine  ← fast string ops, no Python overhead
    └─ CSS selector eng  ← battle-tested scraper crate
```

Python objects returned are **lightweight wrappers**: a `NodeId` (8 bytes) plus a shared reference to the Rust tree. No data is copied from Rust to Python.

---

## License

MIT © Bruno Lima
