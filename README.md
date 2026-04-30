# xhtml

[![CI](https://github.com/LimaBD/xhtml/actions/workflows/ci.yml/badge.svg)](https://github.com/LimaBD/xhtml/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/xhtml.svg)](https://pypi.org/project/xhtml/)
[![Python versions](https://img.shields.io/pypi/pyversions/xhtml.svg)](https://pypi.org/project/xhtml/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## You built a fast data pipeline. Then you added an HTML parser.

> **xhtml is ~33× faster than BeautifulSoup4** with a drop-in compatible API.


AI pipelines today scrape thousands — sometimes millions — of pages to feed context into agents, build knowledge bases, run competitive intelligence, and power real-time decision making. The HTTP layer? Async, concurrent, non-blocking. Your infrastructure? Horizontally scaled.

**Then your agent hands the raw HTML to a pure-Python parser, and the whole pipeline grinds to a halt.**

Processing 1,000 pages (100 KB each) with a standard Python parser takes **~37 seconds**. With `xhtml`, it takes **~1.1 seconds**. That is not a micro-optimisation — it is the difference between a pipeline that responds in near-real-time and one that your users are waiting on.

```
1,000 pages × 100 KB each
─────────────────────────────────────────────────────────
standard Python parser   ████████████████████████████████  37 s
xhtml                    █  1.1 s                           (~34× faster)
```

This is not a toy benchmark on contrived data. At scale, **your parser is the bottleneck** — and now it does not have to be.

```python
from xhtml import Xhtml  # one-line drop-in replacement

soup = Xhtml(html, "html.parser")

titles  = soup.find_all("h2", class_="post-title")
link    = soup.select_one("nav a.active")["href"]
summary = soup.find("p", class_="intro").get_text(strip=True)
```

---

## What is xhtml?

`xhtml` is a Python library for parsing and querying HTML/XML, built for developers who cannot afford the performance tax of pure-Python parsing engines. It exposes the same clean, ergonomic API you already know — while a **Rust engine** handles every byte underneath.

Already using BeautifulSoup4 or another Python parser? xhtml is a **single-import swap** — 33× faster, identical API. See [Migration](#migration).

---

## Why xhtml?

### A Python API — with no Python in the hot path

Three classic bottlenecks of pure-Python HTML parsing:

1. **Tokeniser** — walks the document in Python, character-by-character.
2. **Python object tree** — every tag becomes a Python object with GC overhead. A 500 KB page creates ~2,000 objects, fragments the heap, and stresses the garbage collector.
3. **Python query engine** — `find_all("div", class_="foo")` iterates every node in Python, comparing strings one-by-one.

```
    Your Python code
          │
          ▼
  xhtml Python API   ← clean, expressive
          │  PyO3 bindings
          ▼
   Rust engine (_core)
    ├─ html5ever         ← streaming spec-compliant HTML5 parser
    ├─ arena tree        ← memory-contiguous, zero GC pressure
    ├─ DFS query engine  ← fast string ops, no Python overhead
    └─ CSS selector eng  ← battle-tested scraper crate
```

Python objects you get back are **lightweight wrappers** — just a node ID + a shared reference. No data is ever copied from the Rust tree.

### Pydantic-native structured extraction

Turn HTML directly into typed, validated data models — without a single loop. Define what you want; xhtml delivers:

```python
from xhtml.extract import HtmlModel, Field
from typing import List

class Article(HtmlModel):
    title:   str       = Field(selector="h1")
    url:     str       = Field(selector="a.read-more", attr="href", default="#")
    summary: str       = Field(selector="p.intro",     default="")
    tags:    List[str] = Field(selector=".tag",         multiple=True, default_factory=list)

article  = Article.from_html(html)
articles = Article.from_html_list(page_html, item_selector="article.post")
```

---

## Benchmarks

Operations measured on realistic article HTML, 50 iterations, Linux x86\_64, Python 3.12, Intel Core i7:

| Operation                             | pure-Python parser | **xhtml**  | Speedup     |
| ------------------------------------- | ------------------ | ---------- | ----------- |
| `Xhtml(html)` 20 KB                   | 7.1 ms             | 0.21 ms    | **~34×**    |
| `Xhtml(html)` 100 KB                  | 37 ms              | 1.1 ms     | **~33×**    |
| `Xhtml(html)` 500 KB                  | 188 ms             | 5.4 ms     | **~35×**    |
| `find_all("a")` 100 KB                | 38 ms              | 1.3 ms     | **~29×**    |
| `find_all(class_="title")` 100 KB     | 39 ms              | 1.2 ms     | **~33×**    |
| `select("article h2.title")` 100 KB  | 42 ms              | 1.2 ms     | **~36×**    |
| `get_text()` full page 100 KB         | 37 ms              | 1.1 ms     | **~34×**    |
| **Process 1,000 pages × 100 KB**      | **~37 s**          | **~1.1 s** | **~34×**    |

> Benchmarks run on Linux x86\_64, Python 3.12, Intel Core i7.
> Run your own: `python tests/benchmark.py`

### Comparison with popular alternatives

| Library                 | Speed      | Expressive API       | Structured extraction | Migration effort |
| ----------------------- | ---------- | -------------------- | --------------------- | ---------------- |
| Pure-Python html.parser | 1×         | ✅                   | ❌                    | —                |
| **xhtml**               | **~34×**   | ✅ same interface    | ✅ Pydantic-native    | **minimal**      |
| lxml                    | ~5×        | ⚠️ ElementTree      | ❌                    | high             |
| selectolax              | ~12×       | ⚠️ Limited          | ❌                    | high             |
| parsel                  | ~7×        | ⚠️ XPath-centric    | ❌                    | high             |
| html5-parser            | ~8×        | ❌ Parse only        | ❌                    | n/a              |

---

## Installation

```bash
pip install xhtml
```

Pre-compiled wheels ship for:

- Linux x86\_64 / aarch64 (manylinux)
- macOS x86\_64 / arm64 (M1 / M2 / M3)
- Windows x86\_64

No Rust toolchain required. No system dependencies.

---

## Built for the AI era

Modern AI applications do not scrape one page — they scrape *millions*. Whether you are building a RAG pipeline, a web-crawling agent, competitive intelligence tooling, or a data extraction service, the HTML parsing layer is the silent tax on every operation.

**At 34× the throughput of a standard Python parser**, xhtml turns that tax into a rounding error.

### Common patterns

**Async agent pipeline — feed an LLM from thousands of URLs**

```python
import asyncio, httpx
from xhtml.extract import HtmlModel, Field
from typing import List

class PageContent(HtmlModel):
    title:    str       = Field(selector="h1")
    body:     str       = Field(selector="article, main, .content", default="")
    links:    List[str] = Field(selector="a", attr="href", multiple=True, default_factory=list)

async def fetch_and_parse(url: str, client: httpx.AsyncClient) -> PageContent:
    resp = await client.get(url, timeout=10)
    return PageContent.from_html(resp.text)

async def scrape_all(urls: list[str]) -> list[PageContent]:
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*[fetch_and_parse(u, client) for u in urls])
```

**Bulk pipeline — max CPU throughput with threads**

```python
from xhtml.extract import HtmlModel, Field
import concurrent.futures

class Product(HtmlModel):
    name:  str   = Field(selector="h1.product-name")
    price: float = Field(selector=".price", transform=lambda s: float(s.lstrip("$")))
    sku:   str   = Field(selector="[data-sku]", attr="data-sku", default="")

with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    products = list(pool.map(lambda h: Product.from_html(h), raw_html_pages))
```

**Competitive intelligence — structured extraction at scale**

```python
from xhtml import Xhtml

def extract_pricing(html: str) -> dict:
    soup  = Xhtml(html)
    plans = {}
    for card in soup.select(".pricing-card"):
        name  = card.select_one(".plan-name").get_text(strip=True)
        price = card.select_one(".price").get_text(strip=True)
        plans[name] = price
    return plans
```

---

## Quick start

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
    <p class="intro">A short intro paragraph.</p>
  </body>
</html>
"""

soup = Xhtml(html, "html.parser")

# Find by tag & class
h1 = soup.find("h1", class_="hero")
print(h1.get_text())                    # Welcome
print(h1["class"])                      # ['title', 'hero']

# CSS selectors
active = soup.select_one("ul#nav a.active")
print(active["href"])                   # /about
print([a["href"] for a in soup.select("ul a")])  # ['/home', '/about']

# Tree navigation
print(h1.parent.name)                   # body
print(list(h1.strings))                 # ['Welcome']

# Intro text
print(soup.find("p", class_="intro").get_text(strip=True))
```

---

## Structured extraction with Pydantic

`xhtml.extract` lets you declare **typed data models** and fill them from HTML in a single call — no loops, no scattered `.get_text()`, no manual attribute access.

### Basic model

```python
from xhtml.extract import HtmlModel, Field

class Product(HtmlModel):
    name:  str   = Field(selector="h1.product-name")
    price: float = Field(
        selector=".price",
        transform=lambda s: float(s.replace("$", "").replace(",", "")),
    )
    image: str   = Field(selector="img.hero", attr="src", default="")
    in_stock: bool = Field(
        selector=".stock-badge",
        transform=lambda s: "in stock" in s.lower(),
        default=False,
    )

product = Product.from_html(html)
print(product.name)       # "Rust in Action"
print(product.price)      # 29.99
print(product.in_stock)   # True
```

### Extracting repeated items

```python
from typing import List

class SearchResult(HtmlModel):
    title: str       = Field(selector="h3")
    url:   str       = Field(selector="a",      attr="href", default="")
    blurb: str       = Field(selector="p.desc", default="")

# One model per matching element
results = SearchResult.from_html_list(page_html, item_selector=".result-card")
for r in results:
    print(r.title, r.url)
```

### From an already-parsed tag

```python
soup = Xhtml(page_html, "html.parser")
for card in soup.select(".result-card"):
    result = SearchResult.from_tag(card)
    print(result.title)
```

### Field options

| Parameter           | Type                            | Description                                                          |
| ------------------- | ------------------------------- | -------------------------------------------------------------------- |
| `selector`        | `str`                         | CSS selector to locate the element                                   |
| `attr`            | `str \| None`                  | Attribute to read (`"href"`, `"src"`, …). `None` = inner text |
| `multiple`        | `bool`                        | Return a `List` of all matches instead of the first                |
| `strip`           | `bool`                        | Strip surrounding whitespace from text (default `True`)            |
| `transform`       | `Callable[[str], Any] \| None` | Post-process each raw string value                                   |
| `default`         | `Any`                         | Value used when no element is found                                  |
| `default_factory` | `Callable`                    | Factory for mutable defaults (e.g.`list`)                          |
| `description`     | `str`                         | Forwarded to Pydantic schema                                         |

---

## Full API reference

### Parsing

```python
from xhtml import Xhtml

# All standard parser names are accepted (xhtml uses the same Rust engine regardless)
soup = Xhtml(html_string, "html.parser")  # recommended
soup = Xhtml(html_string, "lxml")          # same engine, alias for compat
soup = Xhtml(html_string, "html5lib")      # same engine, alias for compat

# Bytes input (encoding auto-detected)
soup = Xhtml(html_bytes, "html.parser")
```

### Searching

```python
# By tag name
soup.find("div")
soup.find_all("a")

# By class
soup.find("p", class_="intro")
soup.find_all(class_="card")

# By id
soup.find(id="main")

# By attribute
soup.find("a", href="/about")
soup.find_all("input", type="text")
soup.find("a", href=True)           # any element that has href
soup.find_all("a", href=re.compile(r"https?://"))  # regex

# Multiple tag names
soup.find_all(["h1", "h2", "h3"])

# CSS selectors
soup.select("div.container > p.intro a")
soup.select_one("#main .title")

# Lambda / callable
soup.find_all(lambda tag: tag.name == "a" and tag.has_attr("data-id"))

# Limit results
soup.find_all("a", limit=5)
```

### Extracting content

```python
tag.get_text()                     # all text, concatenated
tag.get_text(" | ", strip=True)    # separator + strip whitespace
tag.text                           # alias for get_text()
tag.string                         # text if single text child, else None
tag.strings                        # iterator over all text nodes
tag.stripped_strings               # stripped, non-empty strings
```

### Attribute access

```python
tag["href"]                        # raises KeyError if missing
tag.get("href")                    # returns None if missing
tag.get("href", "#")               # custom default value
tag.has_attr("class")              # bool
tag.attrs                          # full dict (class is a list)
tag["class"]                       # list: ["foo", "bar"]
```

### Tree navigation

```python
tag.parent                         # immediate parent Tag
tag.parents                        # generator up to root
tag.children                       # direct children (generator)
tag.contents                       # direct children (list)
tag.descendants                    # all descendants (generator)
tag.next_sibling                   # next sibling node
tag.previous_sibling               # previous sibling node
tag.next_siblings                  # generator of next siblings
tag.previous_siblings              # generator of previous siblings

tag.find_parent("div")
tag.find_parents("div", limit=2)
tag.find_next_sibling("p")
tag.find_next_siblings("p")
```

### Rendering

```python
str(tag)                           # outer HTML
tag.encode("utf-8")                # outer HTML as bytes
tag.decode_contents()              # inner HTML (children only)
tag.prettify()                     # indented HTML
```

---

## Migration

If you already use `beautifulsoup4`, switching to xhtml takes **one import line**:

```python
# Before
from bs4 import BeautifulSoup

# After — only this line changes
from xhtml import Xhtml
```

The parsing, searching, and navigation API is designed to behave identically. Run your existing test suite — it should pass without changes.

### Currently unsupported (v0.x — planned for v0.2)

| Feature                                                              | Workaround                               |
| -------------------------------------------------------------------- | ---------------------------------------- |
| In-place tree modification (`tag.decompose()`, `insert()`, etc.) | Parse result, transform in Python        |
| `SoupStrainer`                                                     | Use `find_all` with `limit=`         |
| `prettify()` with precise indent rules                             | Use `str(tag)` + a dedicated formatter |
| Callable `formatter` in `encode()`                               | Post-process in Python                   |

---

## Development setup

### Prerequisites

- Rust ≥ 1.75 — [install rustup](https://rustup.rs)
- Python ≥ 3.8
- `pip install maturin pydantic`

### Build & install for development

```bash
git clone https://github.com/LimaBD/xhtml
cd xhtml
bash scripts/dev_install.sh
```

Or manually:

```bash
pip install maturin
maturin develop --release
```

### Run tests

```bash
bash scripts/run_tests.sh

# Or directly
pytest tests/
```

### Run benchmarks

```bash
bash scripts/run_benchmarks.sh

# Custom iteration count
bash scripts/run_benchmarks.sh 500
```

### Project structure

```
xhtml/
├── Cargo.toml                ← Rust package definition
├── pyproject.toml            ← Python package (maturin build system)
├── native/
│   ├── lib.rs                ← PyO3 module: RustDocument, RustNode, RustQuery
│   └── query.rs              ← DFS search engine + CSS match logic
├── src/
│   └── xhtml/
│       ├── __init__.py       ← Public API surface
│       ├── element.py        ← Tag, NavigableString, Xhtml wrappers
│       ├── extract.py        ← Pydantic-based structured extraction
│       └── _compat.py        ← Compatibility aliases
├── tests/
│   ├── conftest.py           ← Shared fixtures & HTML samples
│   ├── test_compat.py        ← Parser API tests (dual-mode: xhtml + bs4)
│   ├── test_advanced.py      ← Edge cases, regex, lambdas, iterators
│   ├── test_extract.py       ← Pydantic extraction tests
│   └── benchmark.py          ← Performance benchmark suite
├── scripts/
│   ├── dev_install.sh        ← One-command dev setup
│   ├── build.sh              ← Build release wheel
│   ├── run_tests.sh          ← Run full test suite
│   ├── run_benchmarks.sh     ← Run benchmarks
│   └── publish.sh            ← Publish to PyPI / TestPyPI
└── .github/workflows/
    ├── ci.yml                ← Tests on every push/PR
    └── publish.yml           ← Build + publish wheels on tag
```

---

## Architecture deep-dive

### How the Rust engine works

```
Input HTML string
        │
        ▼
html5ever (Rust) ─── streaming, spec-compliant HTML5 parser ───▶ ego-tree
        │
        ▼
Arc/Rc<Html>  ──  single allocation, all nodes in contiguous memory
        │
 ┌──────┴──────┐
 │  RustNode   │  ── NodeId (8 bytes) + Rc pointer ── Python object cost: ~40 bytes
 └─────────────┘
        │ PyO3
        ▼
     Tag  ──  Python wrapper ── delegates ALL work to Rust via FFI
```

### Memory model

A `Xhtml` object holds one `Rc<Html>` — the entire tree lives once in Rust memory. Every `Tag` you get back is a tiny Python object (a `NodeId` + `Rc` clone). Dereferencing a node is O(1) memory lookup.

Compare this to a pure-Python parser: a typical page creates **~2 000 full Python objects**, each with `name`, `attrs`, `contents`, `parent`, `next_sibling`, `prev_sibling` — all Python attributes, all GC-tracked.

### Query engine

`find_all("div", class_="foo")` compiles to:

```
stack-based DFS over ego-tree nodes
  → match: name == "div" AND "foo" ∈ class_set
  → collect NodeIds → wrap in Tag objects
```

All string comparisons happen in Rust, using LLVM-optimised byte comparison. Python is only invoked to wrap the final results.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repo and create a branch.
2. Make your changes.
3. Run `pytest tests/` — all tests must pass.
4. Run `cargo clippy` — no warnings.
5. Open a PR.

### Reporting issues

Please include:

- The HTML you're parsing (or a minimal repro)
- The output you expected vs. what you got
- Your Python/OS version

---

## License

MIT — see [LICENSE](LICENSE).

---

## Documentation

| Guide | Description |
| ----- | ----------- |
| [Quick Start](docs/quickstart.md) | Get up and running in five minutes |
| [API Reference](docs/api-reference.md) | Complete reference for every method |
| [Structured Extraction](docs/extraction.md) | Pydantic models, Field options, and patterns |
| [Migration Guide](docs/migration.md) | Drop-in replacement from BeautifulSoup / lxml |

---

## Acknowledgements

xhtml is built on these excellent projects:

- [PyO3](https://pyo3.rs) — Rust ↔ Python bindings
- [scraper](https://github.com/causal-agent/scraper) — HTML parsing + CSS selectors
- [html5ever](https://github.com/servo/html5ever) — Spec-compliant HTML5 parser from the Servo project
- [ego-tree](https://github.com/causal-agent/ego-tree) — Arena-allocated tree
- [maturin](https://github.com/PyO3/maturin) — Build Rust extensions for Python
- [Pydantic](https://docs.pydantic.dev) — Structured data validation
