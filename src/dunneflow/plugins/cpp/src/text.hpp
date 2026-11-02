// A source file, read the way the host reads it: `ingest/contract.py:SOURCE_TEXT`.
//
// The host opens a file with `Path.read_text(encoding="utf-8", errors="replace")`, so every
// hash it computes is of text that has had two things done to it, and this reader has to do
// both or the echo check refuses the file as having changed under the run:
//
//   - **Newlines are universal.** `\r\n` and a lone `\r` both become `\n`.
//   - **Invalid UTF-8 is replaced the way Python's decoder replaces it**: one U+FFFD per
//     *maximal subpart* of an ill-formed sequence (Unicode's recommended practice). Written
//     out, as Go's `text.go` writes it, and pinned by `vectors.json`'s `decode` rows.
//
// **libclang parses this text, never the file.** It is handed over as an unsaved file, so
// the positions clang reports and the hash the host checks are of the same characters.

#pragma once

#include <fstream>
#include <sstream>
#include <string>

namespace text {

inline const char* REPLACEMENT = "\xEF\xBF\xBD";

// Python's `bytes.decode("utf-8", errors="replace")`.
inline std::string decode_replacing(const std::string& b) {
    std::string out;
    out.reserve(b.size());
    const size_t n = b.size();
    for (size_t i = 0; i < n;) {
        unsigned char c = static_cast<unsigned char>(b[i]);
        if (c < 0x80) {
            out += static_cast<char>(c);
            i++;
            continue;
        }
        // How many continuation bytes this lead byte wants, and the range the first of
        // them must fall in. The narrower first ranges are what exclude overlongs,
        // surrogates and code points above U+10FFFF.
        int need = 0;
        unsigned char lo = 0x80, hi = 0xBF;
        if (c >= 0xC2 && c <= 0xDF) {
            need = 1;
        } else if (c == 0xE0) {
            need = 2;
            lo = 0xA0;
        } else if ((c >= 0xE1 && c <= 0xEC) || c == 0xEE || c == 0xEF) {
            need = 2;
        } else if (c == 0xED) {
            need = 2;
            hi = 0x9F;
        } else if (c == 0xF0) {
            need = 3;
            lo = 0x90;
        } else if (c >= 0xF1 && c <= 0xF3) {
            need = 3;
        } else if (c == 0xF4) {
            need = 3;
            hi = 0x8F;
        } else {
            // 0x80–0xC1 and 0xF5–0xFF never start a sequence: one replacement each.
            out += REPLACEMENT;
            i++;
            continue;
        }
        size_t j = i + 1;
        bool ok = true;
        for (int k = 0; k < need; k++) {
            if (j >= n) {
                ok = false;
                break;
            }
            unsigned char first = k == 0 ? lo : 0x80, last = k == 0 ? hi : 0xBF;
            unsigned char x = static_cast<unsigned char>(b[j]);
            if (x < first || x > last) {
                ok = false;
                break;
            }
            j++;
        }
        if (ok) {
            out.append(b, i, j - i);
        } else {
            // The lead byte and every valid continuation before the break are one maximal
            // subpart, and one replacement.
            out += REPLACEMENT;
        }
        i = j;
    }
    return out;
}

inline std::string normalise_newlines(const std::string& s) {
    if (s.find('\r') == std::string::npos) return s;
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); i++) {
        if (s[i] == '\r') {
            out += '\n';
            if (i + 1 < s.size() && s[i + 1] == '\n') i++;
        } else {
            out += s[i];
        }
    }
    return out;
}

// The host's `SOURCE_TEXT`: decoded with replacement, newlines normalised.
inline std::string decode(const std::string& raw) { return normalise_newlines(decode_replacing(raw)); }

// Read a file as the host does. False when it could not be read at all.
inline bool read_source(const std::string& path, std::string& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    out = decode(ss.str());
    return true;
}

}  // namespace text
