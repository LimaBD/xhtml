"""
benchmark.py
~~~~~~~~~~~~
Performance benchmarks comparing xhtml to beautifulsoup4.

Usage
-----
    # Quick run (fewer iterations)
    python tests/benchmark.py

    # More accurate (more iterations)
    python tests/benchmark.py --iterations 500

    # JSON output (for CI / comparison)
    python tests/benchmark.py --json

Requires:  pip install beautifulsoup4
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable, Dict, List, Tuple

# ─── Sample HTML pages of different sizes ─────────────────────────────────────

_BASE_ARTICLE = """
<article class="post" id="p{i}">
  <h2 class="title">{title}</h2>
  <p class="lead">{lead}</p>
  <ul>
    <li><a href="/tag/python">Python</a></li>
    <li><a href="/tag/rust" class="hot">Rust</a></li>
    <li><a href="/tag/perf">Performance</a></li>
  </ul>
  <footer><a href="/author/{i}" class="author">Author {i}</a></footer>
</article>
"""


def _build_html(n_articles: int) -> str:
    articles = "\n".join(
        _BASE_ARTICLE.format(
            i=i,
            title=f"Article title number {i} about Python and Rust",
            lead="A short description of the article content. " * 5,
        )
        for i in range(n_articles)
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Benchmark Page</title>
</head>
<body>
  <header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
  <main>{articles}</main>
  <footer class="site-footer"><p>Footer text</p></footer>
</body>
</html>"""


HTML_SMALL  = _build_html(20)    # ~20 KB
HTML_MEDIUM = _build_html(100)   # ~100 KB
HTML_LARGE  = _build_html(500)   # ~500 KB


# ─── Benchmark runner ─────────────────────────────────────────────────────────

def _bench(fn: Callable[[], Any], iterations: int) -> Tuple[float, float, float]:
    """Return (mean_ms, min_ms, max_ms)."""
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    mean = sum(times) / len(times)
    return mean, min(times), max(times)


def _run_suite(name: str, parser_cls: Any, html: str, iters: int) -> Dict[str, float]:
    results: Dict[str, float] = {}

    def parse():
        return parser_cls(html, "html.parser")

    soup = parse()  # warm up

    mean, mn, mx = _bench(parse, iters)
    results["parse_ms"] = mean

    def find_all_a():
        s = parser_cls(html, "html.parser")
        return s.find_all("a")

    mean, mn, mx = _bench(find_all_a, iters)
    results["find_all_a_ms"] = mean

    def find_all_class():
        s = parser_cls(html, "html.parser")
        return s.find_all(class_="title")

    mean, mn, mx = _bench(find_all_class, iters)
    results["find_all_class_ms"] = mean

    def css_select():
        s = parser_cls(html, "html.parser")
        return s.select("article.post h2.title")

    mean, mn, mx = _bench(css_select, iters)
    results["css_select_ms"] = mean

    def get_text():
        s = parser_cls(html, "html.parser")
        return s.get_text()

    mean, mn, mx = _bench(get_text, iters)
    results["get_text_ms"] = mean

    return results


# ─── Report ───────────────────────────────────────────────────────────────────

def _col(width: int, s: str) -> str:
    return s.ljust(width)


def _print_table(bs4_results: Dict, fs_results: Dict, label: str) -> None:
    header = f"\n{'─' * 72}\n  {label}\n{'─' * 72}"
    print(header)
    fmt = "  {:<28} {:>10} {:>10} {:>10}"
    print(fmt.format("Operation", "bs4 (ms)", "xhtml", "Speedup"))
    print("  " + "─" * 68)
    for key in bs4_results:
        b = bs4_results[key]
        f = fs_results[key]
        if f > 0:
            speedup = f"{b / f:.1f}x"
        else:
            speedup = "N/A"
        op = key.replace("_ms", "").replace("_", " ")
        print(fmt.format(op, f"{b:.3f}", f"{f:.3f}", speedup))


def main() -> None:
    parser = argparse.ArgumentParser(description="xhtml benchmarks")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    try:
        from bs4 import BeautifulSoup as BS4  # type: ignore[import]
    except ImportError:
        print("beautifulsoup4 not installed — skipping bs4 baseline.")
        BS4 = None

    from xhtml import Xhtml

    iters = args.iterations
    all_results: Dict[str, Any] = {}

    cases = [
        ("Small HTML (~20 KB, 20 articles)", HTML_SMALL),
        ("Medium HTML (~100 KB, 100 articles)", HTML_MEDIUM),
        ("Large HTML (~500 KB, 500 articles)", HTML_LARGE),
    ]

    for label, html in cases:
        fs_res = _run_suite("xhtml", Xhtml, html, iters)
        if BS4 is not None:
            bs4_res = _run_suite("bs4", BS4, html, iters)
            if not args.json:
                _print_table(bs4_res, fs_res, label)
            all_results[label] = {"bs4": bs4_res, "xhtml": fs_res}
        else:
            if not args.json:
                print(f"\n{label}")
                for k, v in fs_res.items():
                    print(f"  xhtml  {k}: {v:.3f} ms")
            all_results[label] = {"xhtml": fs_res}

    if args.json:
        print(json.dumps(all_results, indent=2))
    else:
        print(f"\n{'─' * 72}")
        print(f"  Iterations per operation: {iters}")
        print(f"  Note: lower ms = faster; speedup = bs4_time / xhtml_time")
        print(f"{'─' * 72}\n")


if __name__ == "__main__":
    main()
