//! `detectors/rust.yaml`, as the host sends it in `open`.
//!
//! The host loads and validates the rules file (`detectors.rules_document`); this reader
//! only reads the keys it acts on. A key it does not know is ignored, and a key it does
//! know in a shape it cannot read is a note on stderr and a rule read as empty — never a
//! guessed default (rule 49).

use crate::json::Value;

#[derive(Debug, Clone, Default)]
pub struct BoundaryRule {
    pub kind: String,
    pub direction: String,
    pub salience: String,
    pub exact: Vec<String>,
    pub prefix: Vec<String>,
    pub method: Vec<String>,
    pub contains: Vec<String>,
    pub target_arg: Option<i64>,
}

#[derive(Debug, Clone, Default)]
pub struct NetLibrary {
    pub prefix: String,
    pub protocol: String,
    pub is_async: bool,
}

#[derive(Debug, Clone, Default)]
pub struct Rules {
    pub boundaries: Vec<BoundaryRule>,
    pub entry_names: Vec<String>,
    pub builtins: Vec<String>,
    /// Longest prefix first, as `load_rules` sorts them.
    pub net: Vec<NetLibrary>,
    pub verbs: Vec<String>,
}

impl Rules {
    pub fn parse(raw: Option<&Value>) -> Rules {
        let mut r = Rules::default();
        let Some(raw) = raw else { return r };
        for b in raw.get("boundaries").map(Value::as_arr).unwrap_or(&[]) {
            let s = |k: &str| b.get(k).and_then(Value::as_str).unwrap_or("").to_owned();
            let l = |k: &str| b.get(k).map(Value::strings).unwrap_or_default();
            let mut rule = BoundaryRule {
                kind: s("kind"),
                direction: s("direction"),
                salience: s("salience"),
                exact: l("exact"),
                prefix: l("prefix"),
                method: l("method"),
                contains: l("contains"),
                target_arg: b.get("target_arg").and_then(Value::as_i64),
            };
            if rule.direction.is_empty() {
                rule.direction = "BOTH".into();
            }
            if rule.salience.is_empty() {
                rule.salience = "normal".into();
            }
            r.boundaries.push(rule);
        }
        r.entry_names = raw.get("entry_names").map(Value::strings).unwrap_or_default();
        r.builtins = raw.get("builtins").map(Value::strings).unwrap_or_default();
        if let Some(net) = raw.get("network") {
            if let Some(Value::Obj(libs)) = net.get("libraries") {
                for (prefix, lib) in libs {
                    r.net.push(NetLibrary {
                        prefix: prefix.clone(),
                        protocol: lib.get("protocol").and_then(Value::as_str).unwrap_or("").into(),
                        is_async: lib.get("async").and_then(Value::as_bool).unwrap_or(false),
                    });
                }
            }
            r.verbs = net.get("verbs").map(Value::strings).unwrap_or_default();
        }
        r.net.sort_by(|a, b| b.prefix.len().cmp(&a.prefix.len()).then(a.prefix.cmp(&b.prefix)));
        r
    }
}
