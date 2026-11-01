//! The comments `syn` does not keep.
//!
//! A doc comment (`///`, `//!`, `/** */`, `/*! */`) is an attribute and reaches the reader as
//! `#[doc = "…"]` on the item it documents; every other comment is not a token at all and
//! is gone by the time there is a tree. So this is a scanner over the text, and the only
//! thing it has to get right is what is *not* a comment: a `//` inside a string, a raw
//! string, a byte string or a character literal, and a lifetime that looks like the start
//! of a character literal (`'a`).
//!
//! Block comments nest in Rust, unlike C.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Found {
    pub text: String,
    pub line: i64,
    /// The comment stands on a line of its own.
    pub leading: bool,
}

pub fn scan(src: &str) -> Vec<Found> {
    let b = src.as_bytes();
    let mut out = Vec::new();
    let mut i = 0usize;
    let mut line: i64 = 1;
    let mut line_start = 0usize;
    while i < b.len() {
        let c = b[i];
        match c {
            b'\n' => {
                line += 1;
                i += 1;
                line_start = i;
            }
            b'/' if b.get(i + 1) == Some(&b'/') => {
                let end = src[i..].find('\n').map(|n| i + n).unwrap_or(b.len());
                let body = &src[i + 2..end];
                let doc = body.starts_with('/') && !body.starts_with("//") || body.starts_with('!');
                if !doc {
                    let text = body.trim();
                    if !text.is_empty() {
                        out.push(Found {
                            text: text.to_owned(),
                            line,
                            leading: src[line_start..i].trim().is_empty(),
                        });
                    }
                }
                i = end;
            }
            b'/' if b.get(i + 1) == Some(&b'*') => {
                let start_line = line;
                let leading = src[line_start..i].trim().is_empty();
                let begin = i;
                let mut depth = 0usize;
                while i < b.len() {
                    if b[i] == b'/' && b.get(i + 1) == Some(&b'*') {
                        depth += 1;
                        i += 2;
                    } else if b[i] == b'*' && b.get(i + 1) == Some(&b'/') {
                        depth -= 1;
                        i += 2;
                        if depth == 0 {
                            break;
                        }
                    } else {
                        if b[i] == b'\n' {
                            line += 1;
                            line_start = i + 1;
                        }
                        i += 1;
                    }
                }
                let whole = &src[begin..i.min(b.len())];
                let inner = whole.strip_prefix("/*").unwrap_or(whole);
                let inner = inner.strip_suffix("*/").unwrap_or(inner);
                let doc = (inner.starts_with('*') && !inner.starts_with("**") && inner != "*")
                    || inner.starts_with('!');
                let text = inner.trim();
                if !doc && !text.is_empty() {
                    out.push(Found { text: text.to_owned(), line: start_line, leading });
                }
            }
            b'"' => {
                i = skip_string(b, i + 1, &mut line, &mut line_start);
            }
            b'\'' => {
                i = skip_char_or_lifetime(b, i);
            }
            _ if is_word(c) => {
                // Only at a word's start can `r`, `b` or `c` open a raw, byte or C string;
                // `bar"` is an identifier and then a string.
                let starts = i == 0 || !is_word(b[i - 1]);
                if starts && is_raw_start(b, i) {
                    i = skip_raw(b, i, &mut line, &mut line_start);
                } else if starts && matches!(c, b'b' | b'c') && b.get(i + 1) == Some(&b'"') {
                    i = skip_string(b, i + 2, &mut line, &mut line_start);
                } else if starts && c == b'b' && b.get(i + 1) == Some(&b'\'') {
                    i = skip_char_or_lifetime(b, i + 1);
                } else {
                    while i < b.len() && is_word(b[i]) {
                        i += 1;
                    }
                }
            }
            _ => i += 1,
        }
    }
    out
}

fn is_word(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

/// `r"`, `r#"`, `br"`, `br#"`, `cr"`, `cr#"`.
fn is_raw_start(b: &[u8], i: usize) -> bool {
    let mut j = i;
    if matches!(b.get(j), Some(b'b') | Some(b'c')) {
        j += 1;
    }
    if b.get(j) != Some(&b'r') {
        return false;
    }
    j += 1;
    while b.get(j) == Some(&b'#') {
        j += 1;
    }
    b.get(j) == Some(&b'"')
}

fn skip_raw(b: &[u8], mut i: usize, line: &mut i64, line_start: &mut usize) -> usize {
    while b[i] != b'r' {
        i += 1;
    }
    i += 1;
    let mut hashes = 0usize;
    while b.get(i) == Some(&b'#') {
        hashes += 1;
        i += 1;
    }
    i += 1; // the opening quote
    while i < b.len() {
        if b[i] == b'\n' {
            *line += 1;
            *line_start = i + 1;
        }
        if b[i] == b'"' && (0..hashes).all(|k| b.get(i + 1 + k) == Some(&b'#')) {
            return i + 1 + hashes;
        }
        i += 1;
    }
    i
}

fn skip_string(b: &[u8], mut i: usize, line: &mut i64, line_start: &mut usize) -> usize {
    while i < b.len() {
        match b[i] {
            b'\\' => i += 2,
            b'"' => return i + 1,
            b'\n' => {
                *line += 1;
                i += 1;
                *line_start = i;
            }
            _ => i += 1,
        }
    }
    i
}

/// `'x'`, `'\n'`, `'\u{1F600}'` are characters; `'a` and `'static` are lifetimes.
fn skip_char_or_lifetime(b: &[u8], i: usize) -> usize {
    if b.get(i + 1) == Some(&b'\\') {
        let mut j = i + 2;
        while j < b.len() && b[j] != b'\'' && b[j] != b'\n' {
            j += 1;
        }
        return j + 1;
    }
    // One character (possibly multi-byte) then a quote is a character literal.
    let mut j = i + 1;
    if j < b.len() {
        j += utf8_len(b[j]);
    }
    if b.get(j) == Some(&b'\'') {
        return j + 1;
    }
    i + 1
}

fn utf8_len(first: u8) -> usize {
    match first {
        0x00..=0x7F => 1,
        0xC0..=0xDF => 2,
        0xE0..=0xEF => 3,
        _ => 4,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn what_is_not_a_comment_is_left_alone() {
        let src = "/// doc\n//! inner\nfn f<'a>(x: &'a str) -> char { // real\n    \
                   let u = \"http://x\"; let r = r#\"// no\"#; let c = '/';\n    \
                   /* one /* nested */ still */ let s = b\"//\"; br\"x\"; 'x' }\n\
                   /** doc block */ /*! inner block */ /**/ /***/\n";
        let got: Vec<(String, i64, bool)> =
            scan(src).into_iter().map(|f| (f.text, f.line, f.leading)).collect();
        assert_eq!(
            got,
            vec![
                ("real".to_owned(), 3, false),
                ("one /* nested */ still".to_owned(), 5, true),
                ("*".to_owned(), 6, false),
            ]
        );
    }
}
