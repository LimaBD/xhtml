use ego_tree::NodeId;
use scraper::{ElementRef, Html};
use std::rc::Rc;

use crate::{RustNode, RustQuery};

// ─── Public API ──────────────────────────────────────────────────────────────

pub fn find_in_doc(html: &Rc<Html>, query: &RustQuery) -> Option<RustNode> {
    find_all_in_tree(html, html.tree.root().id(), query, 1)
        .into_iter()
        .next()
}

pub fn find_all_in_doc(html: &Rc<Html>, query: &RustQuery, limit: usize) -> Vec<RustNode> {
    find_all_in_tree(html, html.tree.root().id(), query, limit)
}

pub fn find_in_node(html: &Rc<Html>, start: NodeId, query: &RustQuery) -> Option<RustNode> {
    find_all_in_tree(html, start, query, 1).into_iter().next()
}

pub fn find_all_in_node(
    html: &Rc<Html>,
    start: NodeId,
    query: &RustQuery,
    limit: usize,
) -> Vec<RustNode> {
    find_all_in_tree(html, start, query, limit)
}

// ─── Core DFS search ─────────────────────────────────────────────────────────

fn find_all_in_tree(
    html: &Rc<Html>,
    start: NodeId,
    query: &RustQuery,
    limit: usize,
) -> Vec<RustNode> {
    let mut results = Vec::new();

    // Seed the stack with REVERSED children so stack.pop() gives the first child first.
    let seed_ids: Vec<NodeId> = html
        .tree
        .get(start)
        .map(|n| n.children().map(|c| c.id()).collect::<Vec<_>>())
        .unwrap_or_default();

    let mut stack: Vec<NodeId> = seed_ids.into_iter().rev().collect();

    while let Some(node_id) = stack.pop() {
        // Check if this element matches
        let is_match = {
            let node = match html.tree.get(node_id) {
                Some(n) => n,
                None => continue,
            };
            match ElementRef::wrap(node) {
                Some(el) => matches_query(&el, query),
                None => false,
            }
        };

        if is_match {
            results.push(RustNode {
                html: Rc::clone(html),
                node_id,
            });
            if limit > 0 && results.len() >= limit {
                return results;
            }
        }

        // Push children in REVERSED order so we pop them in forward (document) order.
        if query.recursive {
            let child_ids: Vec<NodeId> = html
                .tree
                .get(node_id)
                .map(|n| n.children().map(|c| c.id()).collect::<Vec<_>>())
                .unwrap_or_default();
            stack.extend(child_ids.into_iter().rev());
        }
    }

    results
}

// ─── Query matching ──────────────────────────────────────────────────────────

pub(crate) fn matches_query(el: &ElementRef<'_>, query: &RustQuery) -> bool {
    // 1. Tag name(s)
    if !query.names.is_empty() {
        let tag = el.value().name();
        if !query.names.iter().any(|n| n == "*" || n == tag) {
            return false;
        }
    }

    // 2. id attribute
    if let Some(ref required_id) = query.id {
        match el.value().attr("id") {
            Some(v) if v == required_id.as_str() => {}
            _ => return false,
        }
    }

    // 3. CSS classes (ALL must be present)
    if !query.classes.is_empty() {
        let class_str = el.value().attr("class").unwrap_or("");
        let el_classes: Vec<&str> = class_str.split_whitespace().collect();
        for req in &query.classes {
            if !el_classes.contains(&req.as_str()) {
                return false;
            }
        }
    }

    // 4. Additional attributes
    for (attr_name, possible_values) in &query.attrs {
        match el.value().attr(attr_name.as_str()) {
            None => return false,
            Some(val) => {
                if !possible_values.is_empty() && !possible_values.iter().any(|v| v.as_str() == val)
                {
                    return false;
                }
            }
        }
    }

    true
}
