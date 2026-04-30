"""
xhtml — fast, ergonomic HTML/XML parsing for Python with a Rust core.

Parse HTML, search the tree, and extract structured data:

    from xhtml import Xhtml

    soup = Xhtml(html, "html.parser")
    title = soup.find("h1", class_="title").get_text()
    links = [a["href"] for a in soup.select("nav a")]

For structured extraction, see :mod:`xhtml.extract`.
"""

from xhtml.element import Xhtml, Tag, NavigableString, ResultSet

__all__ = ["Xhtml", "Tag", "NavigableString", "ResultSet"]
__version__ = "0.1.0"
__author__ = "xhtml contributors"
