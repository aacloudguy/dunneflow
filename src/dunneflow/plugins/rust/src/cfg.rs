//! `#[cfg(...)]`, evaluated in three values, against one fixed world.
//!
//! **Two questions are asked of a predicate and neither is a guess.**
//!
//! - *Is this item test code?* `#[cfg(test)]` and `#[cfg(all(test, ...))]` are; an item is
//!   left out as a test only where its predicate is **false** once `test` is false, so
//!   `#[cfg(not(test))]` and `#[cfg(any(test, feature = "x"))]` stay in the map.
//! - *Is this item the reference target's?* Tom's decision for Go (2026-11-01), carried to
//!   Rust: a definition per platform is drawn to its **linux/x86_64** one. `target_os`,
//!   `unix`, `windows`, `target_family` and `target_arch` are known there; a `feature`,
//!   a `debug_assertions` or anything else this file has not been taught is *unknown*,
//!   and an unknown predicate keeps the item rather than dropping it (rule 1 cuts the
//!   other way for a definition: dropping one draws a smaller program).
//!
//! Kleene's three values, so `all(unknown, false)` is false and `any(unknown, true)` true.

use syn::punctuated::Punctuated;
use syn::{Attribute, Expr, ExprLit, Lit, Meta, Token};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tri {
    True,
    False,
    Unknown,
}

impl Tri {
    /// Kleene's conjunction.
    pub fn and(self, other: Tri) -> Tri {
        match (self, other) {
            (Tri::False, _) | (_, Tri::False) => Tri::False,
            (Tri::Unknown, _) | (_, Tri::Unknown) => Tri::Unknown,
            _ => Tri::True,
        }
    }

    fn not(self) -> Tri {
        match self {
            Tri::True => Tri::False,
            Tri::False => Tri::True,
            Tri::Unknown => Tri::Unknown,
        }
    }
}

/// Which world a predicate is evaluated in.
#[derive(Debug, Clone, Copy)]
pub struct World {
    /// `Some(false)`: the program as shipped. `None`: `test` is not asked about.
    pub test: Option<bool>,
    /// Evaluate the platform predicates against linux/x86_64.
    pub reference_target: bool,
}

pub const SHIPPED: World = World { test: Some(false), reference_target: false };
pub const REFERENCE: World = World { test: Some(false), reference_target: true };

fn string_value(e: &Expr) -> Option<String> {
    match e {
        Expr::Lit(ExprLit { lit: Lit::Str(s), .. }) => Some(s.value()),
        _ => None,
    }
}

pub fn eval(meta: &Meta, w: World) -> Tri {
    match meta {
        Meta::Path(p) => {
            let name = p.get_ident().map(|i| i.to_string()).unwrap_or_default();
            match (name.as_str(), w.test) {
                ("test", Some(t)) => bool3(t),
                ("unix", _) if w.reference_target => Tri::True,
                ("windows", _) if w.reference_target => Tri::False,
                _ => Tri::Unknown,
            }
        }
        Meta::NameValue(nv) => {
            if !w.reference_target {
                return Tri::Unknown;
            }
            let name = nv.path.get_ident().map(|i| i.to_string()).unwrap_or_default();
            let Some(v) = string_value(&nv.value) else { return Tri::Unknown };
            match name.as_str() {
                "target_os" => bool3(v == "linux"),
                "target_family" => bool3(v == "unix"),
                "target_arch" => bool3(v == "x86_64"),
                "target_pointer_width" => bool3(v == "64"),
                "target_endian" => bool3(v == "little"),
                "target_env" => bool3(v == "gnu"),
                "target_vendor" => bool3(v == "unknown"),
                _ => Tri::Unknown,
            }
        }
        Meta::List(list) => {
            let name = list.path.get_ident().map(|i| i.to_string()).unwrap_or_default();
            let Ok(args) = list.parse_args_with(Punctuated::<Meta, Token![,]>::parse_terminated)
            else {
                return Tri::Unknown;
            };
            let vals: Vec<Tri> = args.iter().map(|m| eval(m, w)).collect();
            match name.as_str() {
                "not" if vals.len() == 1 => vals[0].not(),
                "all" => {
                    if vals.contains(&Tri::False) {
                        Tri::False
                    } else if vals.contains(&Tri::Unknown) {
                        Tri::Unknown
                    } else {
                        Tri::True
                    }
                }
                "any" => {
                    if vals.contains(&Tri::True) {
                        Tri::True
                    } else if vals.contains(&Tri::Unknown) {
                        Tri::Unknown
                    } else {
                        Tri::False
                    }
                }
                _ => Tri::Unknown,
            }
        }
    }
}

fn bool3(b: bool) -> Tri {
    if b {
        Tri::True
    } else {
        Tri::False
    }
}

/// Every `#[cfg(...)]` on an item, conjoined. No `cfg` at all is `True`.
pub fn item(attrs: &[Attribute], w: World) -> Tri {
    let mut out = Tri::True;
    for a in attrs {
        if !a.path().is_ident("cfg") {
            continue;
        }
        let v = a.parse_args::<Meta>().map(|m| eval(&m, w)).unwrap_or(Tri::Unknown);
        out = match (out, v) {
            (Tri::False, _) | (_, Tri::False) => Tri::False,
            (Tri::Unknown, _) | (_, Tri::Unknown) => Tri::Unknown,
            _ => Tri::True,
        };
    }
    out
}

/// Test code: `#[test]` (and any `…::test` harness attribute, `#[tokio::test]` among them),
/// or a `cfg` that is false once `test` is.
pub fn is_test(attrs: &[Attribute]) -> bool {
    let harness = attrs.iter().any(|a| {
        a.path().segments.last().is_some_and(|s| s.ident == "test")
    });
    harness || item(attrs, SHIPPED) == Tri::False && item(attrs, World { test: Some(true), reference_target: false }) != Tri::False
}

/// Whether a platform predicate names the reference target at all: an item with such a
/// predicate is one of a per-platform set, and `how` counts the set.
pub fn platform_shaped(attrs: &[Attribute]) -> bool {
    attrs.iter().filter(|a| a.path().is_ident("cfg")).any(|a| {
        let t = a.parse_args::<Meta>().map(|m| eval(&m, REFERENCE)).unwrap_or(Tri::Unknown);
        let s = a.parse_args::<Meta>().map(|m| eval(&m, SHIPPED)).unwrap_or(Tri::Unknown);
        t != Tri::Unknown && s == Tri::Unknown
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn attrs(src: &str) -> Vec<Attribute> {
        let f: syn::ItemFn = syn::parse_str(&format!("{src} fn f() {{}}")).unwrap();
        f.attrs
    }

    #[test]
    fn test_code_is_what_is_false_without_test() {
        assert!(is_test(&attrs("#[cfg(test)]")));
        assert!(is_test(&attrs("#[cfg(all(test, unix))]")));
        assert!(is_test(&attrs("#[test]")));
        assert!(is_test(&attrs("#[tokio::test]")));
        assert!(!is_test(&attrs("#[cfg(not(test))]")));
        assert!(!is_test(&attrs("#[cfg(any(test, feature = \"x\"))]")));
        assert!(!is_test(&attrs("#[inline]")));
    }

    #[test]
    fn the_reference_target_is_linux_x86_64_and_the_unknown_is_kept() {
        assert_eq!(item(&attrs("#[cfg(target_os = \"linux\")]"), REFERENCE), Tri::True);
        assert_eq!(item(&attrs("#[cfg(target_os = \"macos\")]"), REFERENCE), Tri::False);
        assert_eq!(item(&attrs("#[cfg(windows)]"), REFERENCE), Tri::False);
        assert_eq!(item(&attrs("#[cfg(not(windows))]"), REFERENCE), Tri::True);
        assert_eq!(item(&attrs("#[cfg(feature = \"x\")]"), REFERENCE), Tri::Unknown);
        assert_eq!(item(&attrs("#[cfg(all(unix, feature = \"x\"))]"), REFERENCE), Tri::Unknown);
        assert_eq!(item(&attrs("#[cfg(all(windows, feature = \"x\"))]"), REFERENCE), Tri::False);
        assert!(platform_shaped(&attrs("#[cfg(target_os = \"macos\")]")));
        assert!(!platform_shaped(&attrs("#[cfg(feature = \"x\")]")));
    }
}
