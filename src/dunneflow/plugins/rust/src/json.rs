//! JSON, as much of it as the protocol needs, written here rather than vendored.
//!
//! serde would be a fourth vendored crate and a procedural macro — a build step running
//! somebody's code in order to read code — for a wire whose every frame this reader either
//! builds itself (`facts.rs` is generated from `schema.py`) or reads a handful of keys out
//! of. So the decoder is a plain recursive one and the encoder is a trait.
//!
//! **`write_str` is the one place a string is escaped.** A stray control character or a
//! lone surrogate in a frame is a line the host cannot read, and it refuses the language
//! once and loudly; so every string on the wire passes through here, and nothing else in
//! this reader writes a quote.

use std::collections::BTreeMap;

/// A decoded frame, or any part of one. Objects keep their keys in the order read.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Value>),
    Obj(Vec<(String, Value)>),
}

impl Value {
    /// The member `key` of an object, or nothing.
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Obj(members) => members.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_arr(&self) -> &[Value] {
        match self {
            Value::Arr(items) => items,
            _ => &[],
        }
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            Value::Bool(b) => Some(*b),
            _ => None,
        }
    }

    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Value::Num(n) if n.fract() == 0.0 => Some(*n as i64),
            _ => None,
        }
    }

    /// Every string in an array, skipping anything that is not one.
    pub fn strings(&self) -> Vec<String> {
        self.as_arr().iter().filter_map(|v| v.as_str().map(str::to_owned)).collect()
    }
}

/// Decode one frame. An error names the byte offset, because the only person who will
/// read it is somebody looking at the line that caused it.
pub fn parse(text: &str) -> Result<Value, String> {
    let mut p = Parser { s: text.as_bytes(), i: 0 };
    p.ws();
    let v = p.value()?;
    p.ws();
    if p.i != p.s.len() {
        return Err(format!("trailing bytes at {}", p.i));
    }
    Ok(v)
}

struct Parser<'a> {
    s: &'a [u8],
    i: usize,
}

impl Parser<'_> {
    fn ws(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }

    fn eat(&mut self, lit: &str) -> Result<(), String> {
        if self.s[self.i..].starts_with(lit.as_bytes()) {
            self.i += lit.len();
            Ok(())
        } else {
            Err(format!("expected {lit} at {}", self.i))
        }
    }

    fn value(&mut self) -> Result<Value, String> {
        match self.s.get(self.i) {
            None => Err("unexpected end".into()),
            Some(b'n') => self.eat("null").map(|_| Value::Null),
            Some(b't') => self.eat("true").map(|_| Value::Bool(true)),
            Some(b'f') => self.eat("false").map(|_| Value::Bool(false)),
            Some(b'"') => self.string().map(Value::Str),
            Some(b'[') => {
                self.i += 1;
                let mut items = Vec::new();
                self.ws();
                if self.s.get(self.i) == Some(&b']') {
                    self.i += 1;
                    return Ok(Value::Arr(items));
                }
                loop {
                    self.ws();
                    items.push(self.value()?);
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b']') => {
                            self.i += 1;
                            return Ok(Value::Arr(items));
                        }
                        _ => return Err(format!("expected , or ] at {}", self.i)),
                    }
                }
            }
            Some(b'{') => {
                self.i += 1;
                let mut members = Vec::new();
                self.ws();
                if self.s.get(self.i) == Some(&b'}') {
                    self.i += 1;
                    return Ok(Value::Obj(members));
                }
                loop {
                    self.ws();
                    let k = self.string()?;
                    self.ws();
                    self.eat(":")?;
                    self.ws();
                    let v = self.value()?;
                    members.push((k, v));
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b'}') => {
                            self.i += 1;
                            return Ok(Value::Obj(members));
                        }
                        _ => return Err(format!("expected , or }} at {}", self.i)),
                    }
                }
            }
            Some(_) => self.number(),
        }
    }

    fn number(&mut self) -> Result<Value, String> {
        let start = self.i;
        while self.i < self.s.len()
            && matches!(self.s[self.i], b'-' | b'+' | b'.' | b'e' | b'E' | b'0'..=b'9')
        {
            self.i += 1;
        }
        let text = std::str::from_utf8(&self.s[start..self.i]).map_err(|e| e.to_string())?;
        text.parse::<f64>().map(Value::Num).map_err(|_| format!("bad number at {start}"))
    }

    fn hex4(&mut self) -> Result<u32, String> {
        let h = self.s.get(self.i..self.i + 4).ok_or("short \\u escape")?;
        let h = std::str::from_utf8(h).map_err(|e| e.to_string())?;
        self.i += 4;
        u32::from_str_radix(h, 16).map_err(|_| format!("bad \\u escape at {}", self.i))
    }

    fn string(&mut self) -> Result<String, String> {
        self.eat("\"")?;
        let mut out: Vec<u8> = Vec::new();
        loop {
            let c = *self.s.get(self.i).ok_or("unterminated string")?;
            self.i += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let e = *self.s.get(self.i).ok_or("unterminated escape")?;
                    self.i += 1;
                    let ch = match e {
                        b'"' => '"',
                        b'\\' => '\\',
                        b'/' => '/',
                        b'b' => '\u{8}',
                        b'f' => '\u{c}',
                        b'n' => '\n',
                        b'r' => '\r',
                        b't' => '\t',
                        b'u' => {
                            let hi = self.hex4()?;
                            let code = if (0xD800..0xDC00).contains(&hi)
                                && self.s[self.i..].starts_with(b"\\u")
                            {
                                self.i += 2;
                                let lo = self.hex4()?;
                                0x10000 + ((hi - 0xD800) << 10) + (lo.wrapping_sub(0xDC00) & 0x3FF)
                            } else {
                                hi
                            };
                            char::from_u32(code).unwrap_or('\u{FFFD}')
                        }
                        _ => return Err(format!("bad escape at {}", self.i)),
                    };
                    let mut buf = [0u8; 4];
                    out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
                }
                _ => out.push(c),
            }
        }
        String::from_utf8(out).map_err(|e| e.to_string())
    }
}

/// Something that can put itself on the wire.
pub trait ToJson {
    fn write_json(&self, out: &mut String);

    fn to_json(&self) -> String {
        let mut s = String::new();
        self.write_json(&mut s);
        s
    }
}

/// One escaped string, quotes included. ASCII out, so the frame survives any pipe.
pub fn write_str(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 || (c as u32) > 0x7E => {
                let mut buf = [0u16; 2];
                for unit in c.encode_utf16(&mut buf) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `"name": value`, with the comma the previous member needed.
pub fn field<T: ToJson + ?Sized>(out: &mut String, first: &mut bool, name: &str, v: &T) {
    if !*first {
        out.push(',');
    }
    *first = false;
    write_str(out, name);
    out.push(':');
    v.write_json(out);
}

impl ToJson for String {
    fn write_json(&self, out: &mut String) {
        write_str(out, self);
    }
}

impl ToJson for str {
    fn write_json(&self, out: &mut String) {
        write_str(out, self);
    }
}

impl ToJson for i64 {
    fn write_json(&self, out: &mut String) {
        out.push_str(&self.to_string());
    }
}

impl ToJson for usize {
    fn write_json(&self, out: &mut String) {
        out.push_str(&self.to_string());
    }
}

impl ToJson for f64 {
    fn write_json(&self, out: &mut String) {
        if self.is_finite() {
            out.push_str(&format!("{self:?}"));
        } else {
            out.push_str("null");
        }
    }
}

impl ToJson for bool {
    fn write_json(&self, out: &mut String) {
        out.push_str(if *self { "true" } else { "false" });
    }
}

impl<T: ToJson> ToJson for Vec<T> {
    fn write_json(&self, out: &mut String) {
        self.as_slice().write_json(out);
    }
}

impl<T: ToJson> ToJson for [T] {
    fn write_json(&self, out: &mut String) {
        out.push('[');
        for (i, v) in self.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            v.write_json(out);
        }
        out.push(']');
    }
}

impl<T: ToJson, const N: usize> ToJson for [T; N] {
    fn write_json(&self, out: &mut String) {
        self.as_slice().write_json(out);
    }
}

impl<T: ToJson> ToJson for Option<T> {
    fn write_json(&self, out: &mut String) {
        match self {
            Some(v) => v.write_json(out),
            None => out.push_str("null"),
        }
    }
}

impl<T: ToJson> ToJson for BTreeMap<String, T> {
    fn write_json(&self, out: &mut String) {
        out.push('{');
        let mut first = true;
        for (k, v) in self {
            field(out, &mut first, k, v);
        }
        out.push('}');
    }
}

impl ToJson for Value {
    fn write_json(&self, out: &mut String) {
        match self {
            Value::Null => out.push_str("null"),
            Value::Bool(b) => b.write_json(out),
            Value::Num(n) => {
                if n.fract() == 0.0 && n.abs() < 9.0e15 {
                    out.push_str(&(*n as i64).to_string());
                } else {
                    n.write_json(out);
                }
            }
            Value::Str(s) => write_str(out, s),
            Value::Arr(items) => items.write_json(out),
            Value::Obj(members) => {
                out.push('{');
                let mut first = true;
                for (k, v) in members {
                    field(out, &mut first, k, v);
                }
                out.push('}');
            }
        }
    }
}

/// A frame being built: an ordered object whose members are already encoded.
#[derive(Default)]
pub struct Frame {
    body: String,
    first: bool,
}

impl Frame {
    pub fn new(t: &str) -> Frame {
        let mut f = Frame { body: String::from("{"), first: true };
        f.put("t", t);
        f
    }

    pub fn put<T: ToJson + ?Sized>(&mut self, name: &str, v: &T) -> &mut Frame {
        field(&mut self.body, &mut self.first, name, v);
        self
    }

    pub fn finish(mut self) -> String {
        self.body.push('}');
        self.body
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_frame_survives_the_round_trip() {
        let v = parse(r#"{"t":"open","id":3,"files":["a.rs","bé.rs"],"x":{"y":[true,null,-1.5e2]}}"#)
            .unwrap();
        assert_eq!(v.get("t").and_then(Value::as_str), Some("open"));
        assert_eq!(v.get("id").and_then(Value::as_i64), Some(3));
        assert_eq!(v.get("files").unwrap().strings(), vec!["a.rs", "bé.rs"]);
        let back = parse(&v.to_json()).unwrap();
        assert_eq!(back, v);
    }

    #[test]
    fn every_string_leaves_as_ascii() {
        let mut s = String::new();
        write_str(&mut s, "a\"\\\n\u{1}é😀");
        assert_eq!(s, "\"a\\\"\\\\\\n\\u0001\\u00e9\\ud83d\\ude00\"");
        assert_eq!(parse(&s).unwrap(), Value::Str("a\"\\\n\u{1}é😀".into()));
    }
}
