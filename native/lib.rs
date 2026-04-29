use pyo3::prelude::*;
use scraper::{Html, Selector, ElementRef};
use scraper::node::Node;
use ego_tree::NodeId;
use std::rc::Rc;

mod query;

// ─── Core structs ────────────────────────────────────────────────────────────

/// Holds the parsed HTML document; shared (via Rc) across all nodes from it.
#[pyclass(unsendable)]
pub struct RustDocument {
    pub(crate) html: Rc<Html>,
}

/// A single node (element or text) inside the parsed HTML tree.
#[pyclass(unsendable)]
pub struct RustNode {
    pub(crate) html: Rc<Html>,
    pub(crate) node_id: NodeId,
}

/// Describes a find / find_all query (tag name, attributes, classes, id).
#[pyclass]
#[derive(Clone, Debug)]
pub struct RustQuery {
    pub(crate) names: Vec<String>,                    // tag names to match (empty = any)
    pub(crate) attrs: Vec<(String, Vec<String>)>,     // (attr_name, [possible_values])
    pub(crate) classes: Vec<String>,                  // ALL must be present
    pub(crate) id: Option<String>,
    pub(crate) recursive: bool,
}

// ─── RustDocument ────────────────────────────────────────────────────────────

#[pymethods]
impl RustDocument {
    #[new]
    fn new(html_str: &str) -> Self {
        RustDocument {
            html: Rc::new(Html::parse_document(html_str)),
        }
    }

    /// Return a RustNode representing the document root.
    fn root_node(&self) -> RustNode {
        RustNode {
            html: Rc::clone(&self.html),
            node_id: self.html.tree.root().id(),
        }
    }

    fn find(&self, query: &RustQuery) -> Option<RustNode> {
        query::find_in_doc(&self.html, query)
    }

    fn find_all(&self, query: &RustQuery, limit: usize) -> Vec<RustNode> {
        query::find_all_in_doc(&self.html, query, limit)
    }

    fn select(&self, css: &str) -> PyResult<Vec<RustNode>> {
        let selector = Selector::parse(css).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid CSS selector: '{css}'"
            ))
        })?;
        Ok(self
            .html
            .select(&selector)
            .map(|el| RustNode {
                html: Rc::clone(&self.html),
                node_id: el.id(),
            })
            .collect())
    }

    fn select_one(&self, css: &str) -> PyResult<Option<RustNode>> {
        let selector = Selector::parse(css).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid CSS selector: '{css}'"
            ))
        })?;
        Ok(self.html.select(&selector).next().map(|el| RustNode {
            html: Rc::clone(&self.html),
            node_id: el.id(),
        }))
    }

    fn get_text(&self, separator: &str, strip: bool) -> String {
        let texts: Vec<&str> = self.html.root_element().text().collect();
        let result = texts.join(separator);
        if strip {
            result.trim().to_string()
        } else {
            result
        }
    }

    fn to_html(&self) -> String {
        self.html.root_element().html()
    }
}

// ─── RustNode ────────────────────────────────────────────────────────────────

#[pymethods]
impl RustNode {
    fn name(&self) -> String {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return String::new(),
        };
        match ElementRef::wrap(node) {
            Some(el) => el.value().name().to_string(),
            None => String::new(),
        }
    }

    fn attrs(&self) -> Vec<(String, String)> {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return vec![],
        };
        match ElementRef::wrap(node) {
            Some(el) => el
                .value()
                .attrs()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
            None => vec![],
        }
    }

    fn get_attr(&self, key: &str) -> Option<String> {
        let node = self.html.tree.get(self.node_id)?;
        let el = ElementRef::wrap(node)?;
        el.value().attr(key).map(|s| s.to_string())
    }

    fn has_attr(&self, key: &str) -> bool {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return false,
        };
        match ElementRef::wrap(node) {
            Some(el) => el.value().attr(key).is_some(),
            None => false,
        }
    }

    fn get_text(&self, separator: &str, strip: bool) -> String {
        let result = {
            let node = match self.html.tree.get(self.node_id) {
                Some(n) => n,
                None => return String::new(),
            };
            match ElementRef::wrap(node) {
                Some(el) => {
                    let texts: Vec<&str> = el.text().collect();
                    texts.join(separator)
                }
                None => {
                    // Document root node
                    let texts: Vec<&str> = self.html.root_element().text().collect();
                    texts.join(separator)
                }
            }
        };
        if strip {
            result.trim().to_string()
        } else {
            result
        }
    }

    fn to_html(&self) -> String {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return String::new(),
        };
        match ElementRef::wrap(node) {
            Some(el) => el.html(),
            None => self.html.root_element().html(),
        }
    }

    fn inner_html(&self) -> String {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return String::new(),
        };
        match ElementRef::wrap(node) {
            Some(el) => el.inner_html(),
            None => self.html.root_element().inner_html(),
        }
    }

    /// Returns the text content only if the element has exactly one text node.
    fn single_string(&self) -> Option<String> {
        let node = self.html.tree.get(self.node_id)?;
        let el = ElementRef::wrap(node)?;
        let texts: Vec<&str> = el.text().collect();
        if texts.len() == 1 {
            Some(texts[0].to_string())
        } else {
            None
        }
    }

    /// True if this node is an HTML element (vs a text node or document root).
    fn is_tag(&self) -> bool {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return false,
        };
        ElementRef::wrap(node).is_some()
    }

    /// For text/NavigableString nodes — returns their raw text.
    fn text_content(&self) -> String {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return String::new(),
        };
        match node.value() {
            Node::Text(t) => t.to_string(),
            _ => String::new(),
        }
    }

    fn parent(&self) -> Option<RustNode> {
        let parent_id = self.html.tree.get(self.node_id)?.parent()?.id();
        Some(RustNode {
            html: Rc::clone(&self.html),
            node_id: parent_id,
        })
    }

    fn children(&self) -> Vec<RustNode> {
        let node = match self.html.tree.get(self.node_id) {
            Some(n) => n,
            None => return vec![],
        };
        node.children()
            .map(|child| RustNode {
                html: Rc::clone(&self.html),
                node_id: child.id(),
            })
            .collect()
    }

    fn next_sibling(&self) -> Option<RustNode> {
        let sib_id = {
            let node = self.html.tree.get(self.node_id)?;
            node.next_sibling()?.id()
        };
        Some(RustNode {
            html: Rc::clone(&self.html),
            node_id: sib_id,
        })
    }

    fn prev_sibling(&self) -> Option<RustNode> {
        let sib_id = {
            let node = self.html.tree.get(self.node_id)?;
            node.prev_sibling()?.id()
        };
        Some(RustNode {
            html: Rc::clone(&self.html),
            node_id: sib_id,
        })
    }

    fn next_siblings(&self) -> Vec<RustNode> {
        let mut result = Vec::new();
        let mut current_id = {
            self.html
                .tree
                .get(self.node_id)
                .and_then(|n| n.next_sibling())
                .map(|s| s.id())
        };
        while let Some(id) = current_id {
            result.push(RustNode {
                html: Rc::clone(&self.html),
                node_id: id,
            });
            current_id = self
                .html
                .tree
                .get(id)
                .and_then(|n| n.next_sibling())
                .map(|s| s.id());
        }
        result
    }

    fn prev_siblings(&self) -> Vec<RustNode> {
        let mut result = Vec::new();
        let mut current_id = {
            self.html
                .tree
                .get(self.node_id)
                .and_then(|n| n.prev_sibling())
                .map(|s| s.id())
        };
        while let Some(id) = current_id {
            result.push(RustNode {
                html: Rc::clone(&self.html),
                node_id: id,
            });
            current_id = self
                .html
                .tree
                .get(id)
                .and_then(|n| n.prev_sibling())
                .map(|s| s.id());
        }
        result
    }

    fn find(&self, query: &RustQuery) -> Option<RustNode> {
        query::find_in_node(&self.html, self.node_id, query)
    }

    fn find_all(&self, query: &RustQuery, limit: usize) -> Vec<RustNode> {
        query::find_all_in_node(&self.html, self.node_id, query, limit)
    }

    fn select(&self, css: &str) -> PyResult<Vec<RustNode>> {
        let selector = Selector::parse(css).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid CSS selector: '{css}'"
            ))
        })?;

        let ids: Vec<NodeId> = {
            let node = match self.html.tree.get(self.node_id) {
                Some(n) => n,
                None => return Ok(vec![]),
            };
            match ElementRef::wrap(node) {
                Some(el) => el.select(&selector).map(|e| e.id()).collect(),
                None => self.html.select(&selector).map(|e| e.id()).collect(),
            }
        };

        Ok(ids
            .into_iter()
            .map(|id| RustNode {
                html: Rc::clone(&self.html),
                node_id: id,
            })
            .collect())
    }

    fn select_one(&self, css: &str) -> PyResult<Option<RustNode>> {
        let selector = Selector::parse(css).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid CSS selector: '{css}'"
            ))
        })?;

        let result_id: Option<NodeId> = {
            let node = match self.html.tree.get(self.node_id) {
                Some(n) => n,
                None => return Ok(None),
            };
            match ElementRef::wrap(node) {
                Some(el) => el.select(&selector).next().map(|e| e.id()),
                None => self.html.select(&selector).next().map(|e| e.id()),
            }
        };

        Ok(result_id.map(|id| RustNode {
            html: Rc::clone(&self.html),
            node_id: id,
        }))
    }
}

// ─── RustQuery ───────────────────────────────────────────────────────────────

#[pymethods]
impl RustQuery {
    #[new]
    #[pyo3(signature = (names, attrs, classes, id, recursive))]
    fn new(
        names: Vec<String>,
        attrs: Vec<(String, Vec<String>)>,
        classes: Vec<String>,
        id: Option<String>,
        recursive: bool,
    ) -> Self {
        RustQuery {
            names,
            attrs,
            classes,
            id,
            recursive,
        }
    }
}

// ─── Module entry point ──────────────────────────────────────────────────────

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustDocument>()?;
    m.add_class::<RustNode>()?;
    m.add_class::<RustQuery>()?;
    Ok(())
}
