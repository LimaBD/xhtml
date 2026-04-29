# Structured Extraction

`xhtml.extract` provides a declarative, Pydantic-based system for turning raw HTML into typed Python models — no loops, no manual selector bookkeeping, no scattered `.get_text()` calls.

---

## Core concepts

### `HtmlModel`

Subclass `HtmlModel` and declare fields using `Field`. Call class methods to extract data.

```python
from xhtml.extract import HtmlModel, Field

class Article(HtmlModel):
    title:   str = Field(selector="h1.post-title")
    summary: str = Field(selector="p.intro", default="")
```

### `Field`

Declares how a single piece of data should be extracted from the HTML tree.

```python
Field(
    selector,           # CSS selector
    *,
    attr=None,          # attribute to read (None = inner text)
    multiple=False,     # return all matches as a List
    strip=True,         # strip whitespace from text
    transform=None,     # post-process each raw string
    default=...,        # scalar default when element not found
    default_factory=None,  # factory for mutable defaults
    description="",     # forwarded to Pydantic schema
)
```

---

## Field options reference

| Parameter          | Type                          | Default | Description |
| ------------------ | ----------------------------- | ------- | ----------- |
| `selector`         | `str \| None`                  | —       | CSS selector used to locate the element(s). `None` skips extraction entirely. |
| `attr`             | `str \| None`                  | `None`  | Attribute to read (`"href"`, `"src"`, `"data-id"`, …). `None` reads inner text. |
| `multiple`         | `bool`                        | `False` | Collect all matches and return a `List`. When `True`, the field type should be `List[str]` (or `List[T]` with `transform`). |
| `strip`            | `bool`                        | `True`  | Strip leading/trailing whitespace from extracted text. |
| `transform`        | `Callable[[str], Any] \| None` | `None`  | Applied to each raw string after extraction. Use for type conversion, cleaning, etc. |
| `default`          | `Any`                         | `PydanticRequired` | Value used when the selector finds nothing. |
| `default_factory`  | `Callable`                    | `None`  | Factory function for mutable defaults (`list`, `dict`, etc.). |
| `description`      | `str`                         | `""`    | Forwarded to the Pydantic field schema. |

---

## Class methods

### `HtmlModel.from_html(markup, parser="html.parser")` → `T`

Parse a full HTML document and extract one model instance from it.

```python
product = Product.from_html(html_string)
```

### `HtmlModel.from_tag(tag)` → `T`

Extract a model from an already-parsed `Tag`. Useful when you have already parsed the document and want to scope extraction to a specific subtree.

```python
soup = Xhtml(page_html, "html.parser")
for card in soup.select(".product-card"):
    product = Product.from_tag(card)   # scoped to card's subtree
    print(product.name)
```

### `HtmlModel.from_html_list(markup, item_selector, parser="html.parser")` → `List[T]`

Parse a HTML document, find all elements matching `item_selector`, and extract one model per element.

```python
results = SearchResult.from_html_list(
    page_html,
    item_selector=".result-card"
)
```

---

## Examples

### Text extraction

```python
class BlogPost(HtmlModel):
    title:    str = Field(selector="h1.post-title")
    subtitle: str = Field(selector="h2.subtitle", default="")
    body:     str = Field(selector="div.post-body")

post = BlogPost.from_html(html)
print(post.title)
```

### Attribute extraction

```python
class Link(HtmlModel):
    text: str = Field(selector="a.read-more")
    url:  str = Field(selector="a.read-more", attr="href", default="#")
    rel:  str = Field(selector="a.read-more", attr="rel",  default="")

link = Link.from_html(html)
print(link.url)   # "/articles/123"
```

### Type conversion with `transform`

```python
class Listing(HtmlModel):
    price:    float = Field(selector=".price",    transform=lambda s: float(s.lstrip("$").replace(",", "")))
    rating:   int   = Field(selector=".rating",   transform=int)
    in_stock: bool  = Field(selector=".badge",    transform=lambda s: "in stock" in s.lower(), default=False)
    views:    int   = Field(selector=".view-count", transform=lambda s: int(s.replace(",", "").replace(" views", "")))
```

### Extracting multiple values (lists)

```python
from typing import List

class Article(HtmlModel):
    tags:    List[str] = Field(selector=".tag",    multiple=True, default_factory=list)
    images:  List[str] = Field(selector="img",     attr="src", multiple=True, default_factory=list)
    authors: List[str] = Field(selector=".author", multiple=True, default_factory=list)
```

### Transform on multiple values

```python
class DataTable(HtmlModel):
    values: List[int] = Field(
        selector="td.value",
        multiple=True,
        transform=int,
        default_factory=list,
    )
```

### Default values

```python
class Product(HtmlModel):
    # Scalar default — use when element may not exist
    discount: str = Field(selector=".discount-badge", default="")
    stock:    int = Field(selector=".stock-count", transform=int, default=0)

    # Mutable default — use list/dict
    categories: List[str] = Field(selector=".category", multiple=True, default_factory=list)
```

### Full product model example

```python
from xhtml.extract import HtmlModel, Field
from typing import List

class Product(HtmlModel):
    name:        str       = Field(selector="h1.product-name")
    description: str       = Field(selector=".description",    default="")
    price:       float     = Field(selector=".price",          transform=lambda s: float(s.lstrip("$")))
    sku:         str       = Field(selector="[data-sku]",      attr="data-sku", default="")
    image:       str       = Field(selector="img.hero",        attr="src",      default="")
    in_stock:    bool      = Field(selector=".stock-badge",    transform=lambda s: "in stock" in s.lower(), default=False)
    tags:        List[str] = Field(selector=".tag",            multiple=True, default_factory=list)
    buy_url:     str       = Field(selector="a.buy-button",    attr="href",     default="")

product = Product.from_html(html)
print(product.name)
print(product.price)
print(product.tags)

# Serialize to JSON — it's just a Pydantic model
print(product.model_dump_json())
```

### Listing page extraction

```python
class SearchResult(HtmlModel):
    title: str = Field(selector="h3.result-title")
    url:   str = Field(selector="a.result-link", attr="href", default="")
    blurb: str = Field(selector="p.snippet", default="")

results = SearchResult.from_html_list(
    page_html,
    item_selector=".result-card"
)
print(len(results))           # 10
print(results[0].title)
```

---

## Using with AI pipelines

```python
import asyncio, httpx, json
from xhtml.extract import HtmlModel, Field
from typing import List

class PageSummary(HtmlModel):
    title:       str       = Field(selector="h1, title", default="")
    description: str       = Field(selector='meta[name="description"]', attr="content", default="")
    headings:    List[str] = Field(selector="h1, h2, h3", multiple=True, default_factory=list)
    links:       List[str] = Field(selector="a[href]", attr="href", multiple=True, default_factory=list)

async def summarise_page(url: str, client: httpx.AsyncClient) -> PageSummary:
    resp = await client.get(url, timeout=10)
    return PageSummary.from_html(resp.text)

async def build_context(urls: list[str]) -> str:
    async with httpx.AsyncClient() as client:
        pages = await asyncio.gather(*[summarise_page(u, client) for u in urls])
    # Feed structured data to your LLM
    return json.dumps([p.model_dump() for p in pages], indent=2)
```

---

## Pydantic integration

`HtmlModel` is a standard Pydantic `BaseModel`. All Pydantic features work as expected:

```python
# Validation
product = Product.from_html(html)
product.model_validate(product.model_dump())

# JSON serialisation
json_str = product.model_dump_json()

# Schema
print(Product.model_json_schema())

# Optional fields
from typing import Optional

class Item(HtmlModel):
    title: str           = Field(selector="h1")
    badge: Optional[str] = Field(selector=".badge", default=None)
```

---

## Notes

- If a `selector` matches nothing and no `default` or `default_factory` is provided, Pydantic will raise a `ValidationError` for required fields.
- `multiple=True` always returns a list, even if only one element is found — it never returns `None`.
- `transform` receives the already-stripped string (if `strip=True`) and should return the target Python type.
- For attribute extraction, if the attribute is absent on the matched element, an empty string is returned.
