"""
xhtml._compat
~~~~~~~~~~~~~~~~
Compatibility aliases and exception shims.
"""
from xhtml.element import Xhtml, Tag, NavigableString

SoupStrainer = None  # not yet supported
FeatureNotFound = ImportError
ParserRejectedMarkup = ValueError
