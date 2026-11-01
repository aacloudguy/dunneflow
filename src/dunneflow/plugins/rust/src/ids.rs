//! Every id this reader mints, and the hash it echoes: `schema.py`'s, in Rust.
//!
//! **Do not mint an id any other way** (LANGUAGES.md, rule 106). A definition is
//! `(file, qualname[, ordinal])` and a way in is `entrypoint_id(file, …)`, one function
//! each, for every reader including the ones on the far side of a pipe. This is the third
//! mirror of them, after `plugins/typescript/src/ids.ts` and `plugins/go/ids.go`, and it is
//! pinned the same way: `tests/fixtures/ids/vectors.json`, written by the host from
//! `schema.py`, asserted by the tests at the bottom of this file.
//!
//! **BLAKE2b is written by hand** because the reader takes no dependency it does not need,
//! and the digest size is in the parameter block, so an 8-byte digest is **not** a prefix
//! of a 64-byte one. `make_id` joins its parts with NUL at 8 bytes; `hash_source` is 16.

const IV: [u64; 8] = [
    0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
    0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
];

const SIGMA: [[usize; 16]; 12] = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
    [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
    [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
    [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
    [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
    [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
    [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
    [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
    [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
];

fn compress(h: &mut [u64; 8], block: &[u8; 128], t: u64, last: bool) {
    let mut m = [0u64; 16];
    for (i, word) in m.iter_mut().enumerate() {
        *word = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
    }
    let mut v = [0u64; 16];
    v[..8].copy_from_slice(h);
    v[8..].copy_from_slice(&IV);
    v[12] ^= t;
    if last {
        v[14] = !v[14];
    }
    fn g(v: &mut [u64; 16], a: usize, b: usize, c: usize, d: usize, x: u64, y: u64) {
        v[a] = v[a].wrapping_add(v[b]).wrapping_add(x);
        v[d] = (v[d] ^ v[a]).rotate_right(32);
        v[c] = v[c].wrapping_add(v[d]);
        v[b] = (v[b] ^ v[c]).rotate_right(24);
        v[a] = v[a].wrapping_add(v[b]).wrapping_add(y);
        v[d] = (v[d] ^ v[a]).rotate_right(16);
        v[c] = v[c].wrapping_add(v[d]);
        v[b] = (v[b] ^ v[c]).rotate_right(63);
    }
    for s in SIGMA.iter() {
        g(&mut v, 0, 4, 8, 12, m[s[0]], m[s[1]]);
        g(&mut v, 1, 5, 9, 13, m[s[2]], m[s[3]]);
        g(&mut v, 2, 6, 10, 14, m[s[4]], m[s[5]]);
        g(&mut v, 3, 7, 11, 15, m[s[6]], m[s[7]]);
        g(&mut v, 0, 5, 10, 15, m[s[8]], m[s[9]]);
        g(&mut v, 1, 6, 11, 12, m[s[10]], m[s[11]]);
        g(&mut v, 2, 7, 8, 13, m[s[12]], m[s[13]]);
        g(&mut v, 3, 4, 9, 14, m[s[14]], m[s[15]]);
    }
    for i in 0..8 {
        h[i] ^= v[i] ^ v[i + 8];
    }
}

fn blake2b_hex(mut data: &[u8], outlen: usize) -> String {
    let mut h = IV;
    h[0] ^= 0x0101_0000 ^ outlen as u64;
    let mut t: u64 = 0;
    while data.len() > 128 {
        t += 128;
        compress(&mut h, data[..128].try_into().unwrap(), t, false);
        data = &data[128..];
    }
    let mut block = [0u8; 128];
    block[..data.len()].copy_from_slice(data);
    t += data.len() as u64;
    compress(&mut h, &block, t, true);
    let mut out = Vec::with_capacity(64);
    for word in h {
        out.extend_from_slice(&word.to_le_bytes());
    }
    out[..outlen].iter().map(|b| format!("{b:02x}")).collect()
}

pub fn make_id(parts: &[&str]) -> String {
    blake2b_hex(parts.join("\0").as_bytes(), 8)
}

pub fn definition_id(file: &str, qualname: &str, ordinal: i64) -> String {
    if ordinal == 1 {
        make_id(&[file, qualname])
    } else {
        make_id(&[file, qualname, &format!("#{ordinal}")])
    }
}

pub fn entrypoint_id(file: &str, parts: &[&str]) -> String {
    let mut all = vec!["ep", file];
    all.extend_from_slice(parts);
    make_id(&all)
}

pub fn call_site_id(caller_id: &str, callee_expr: &str, ordinal: i64) -> String {
    make_id(&["site", caller_id, callee_expr, &ordinal.to_string()])
}

pub fn control_point_id(routine_id: &str, kind: &str, header: &str, ordinal: i64) -> String {
    make_id(&["control", routine_id, kind, header, &ordinal.to_string()])
}

pub fn hash_source(text: &str) -> String {
    blake2b_hex(text.as_bytes(), 16)
}

#[cfg(test)]
mod tests {
    //! The pins. `vectors.json` is the host's answer to every function above; a tampered
    //! vector was seen to fail before any was believed (rule 59).
    use super::*;
    use crate::json::{parse, Value};
    use crate::text::decode;

    fn vectors() -> Value {
        // `DUNNEFLOW_ID_VECTORS` first, so a tampered copy can be pointed at and seen to
        // fail (rule 59); the checkout's own file otherwise.
        let path = std::env::var("DUNNEFLOW_ID_VECTORS").unwrap_or_else(|_| {
            concat!(env!("CARGO_MANIFEST_DIR"), "/../../../../tests/fixtures/ids/vectors.json").into()
        });
        let text = std::fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("the id vectors at {path}: {e}"));
        parse(&text).unwrap()
    }

    fn s(v: &Value) -> &str {
        v.as_str().unwrap()
    }

    #[test]
    fn every_id_function_agrees_with_schema_py() {
        let v = vectors();
        for row in v.get("make_id").unwrap().as_arr() {
            let parts: Vec<String> = row.as_arr()[0].strings();
            let parts: Vec<&str> = parts.iter().map(String::as_str).collect();
            assert_eq!(make_id(&parts), s(&row.as_arr()[1]), "make_id {parts:?}");
        }
        for row in v.get("definition_id").unwrap().as_arr() {
            let r = row.as_arr();
            assert_eq!(definition_id(s(&r[0]), s(&r[1]), r[2].as_i64().unwrap()), s(&r[3]));
        }
        for row in v.get("entrypoint_id").unwrap().as_arr() {
            let r = row.as_arr();
            let parts = r[1].strings();
            let parts: Vec<&str> = parts.iter().map(String::as_str).collect();
            assert_eq!(entrypoint_id(s(&r[0]), &parts), s(&r[2]));
        }
        for row in v.get("call_site_id").unwrap().as_arr() {
            let r = row.as_arr();
            assert_eq!(call_site_id(s(&r[0]), s(&r[1]), r[2].as_i64().unwrap()), s(&r[3]));
        }
        for row in v.get("control_point_id").unwrap().as_arr() {
            let r = row.as_arr();
            assert_eq!(
                control_point_id(s(&r[0]), s(&r[1]), s(&r[2]), r[3].as_i64().unwrap()),
                s(&r[4])
            );
        }
        for row in v.get("hash_source").unwrap().as_arr() {
            let r = row.as_arr();
            assert_eq!(hash_source(s(&r[0])), s(&r[1]));
        }
    }

    #[test]
    fn every_decoding_agrees_with_pythons_replace() {
        let v = vectors();
        for row in v.get("decode").unwrap().as_arr() {
            let r = row.as_arr();
            let hex = s(&r[0]);
            let bytes: Vec<u8> = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                .collect();
            assert_eq!(decode(&bytes), s(&r[1]), "bytes {hex}");
        }
    }
}
