"""
Shared HTML fixtures for the xhtml test suite.
"""
import pytest
from xhtml import Xhtml

# ─── Reference HTML ──────────────────────────────────────────────────────────

SIMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <div id="main" class="container wrapper">
    <h1 class="title big">Hello World</h1>
    <p class="intro">First paragraph with <em>emphasis</em>.</p>
    <p class="content">Second <b>bold</b> paragraph</p>
    <ul id="nav">
      <li><a href="/page1">Link 1</a></li>
      <li><a href="/page2" class="external">Link 2</a></li>
      <li><a href="/page3" data-id="3">Link 3</a></li>
    </ul>
  </div>
  <footer>
    <a href="/contact" class="footer-link">Contact</a>
  </footer>
</body>
</html>
"""

NESTED_HTML = """
<div class="outer">
  <div class="inner">
    <p id="target">Deep text</p>
  </div>
</div>
"""

SPECIAL_ATTRS_HTML = """
<input type="text" name="q" value="hello" disabled>
<img src="/logo.png" alt="Logo" class="logo img">
<a href="https://example.com" rel="nofollow noopener">External</a>
<span data-value="42" id="counter">42</span>
"""

MULTI_CLASS_HTML = """
<p class="foo bar baz">Triple class</p>
<p class="foo bar">Double class</p>
<p class="foo">Single class</p>
<p class="other">Other</p>
"""

TABLE_HTML = """
<table>
  <thead>
    <tr><th>Name</th><th>Age</th></tr>
  </thead>
  <tbody>
    <tr><td>Alice</td><td>30</td></tr>
    <tr><td>Bob</td><td>25</td></tr>
  </tbody>
</table>
"""


@pytest.fixture
def soup():
    return Xhtml(SIMPLE_HTML, "html.parser")


@pytest.fixture
def nested_soup():
    return Xhtml(NESTED_HTML, "html.parser")


@pytest.fixture
def attrs_soup():
    return Xhtml(SPECIAL_ATTRS_HTML, "html.parser")


@pytest.fixture
def multi_class_soup():
    return Xhtml(MULTI_CLASS_HTML, "html.parser")


@pytest.fixture
def table_soup():
    return Xhtml(TABLE_HTML, "html.parser")
