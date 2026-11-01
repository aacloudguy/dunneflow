// A source file, read the way the host reads it: `ingest/contract.py:SOURCE_TEXT`.
//
// The host opens a file with `Path.read_text(encoding="utf-8", errors="replace")`, so
// every hash it computes is of text that has had two things done to it, and this reader
// has to do both or the echo check refuses the file as having changed under the run:
//
//   - **Newlines are universal.** `\r\n` and a lone `\r` both become `\n`. Measured on
//     uigen when the TypeScript reader skipped this: 2 of 54 files, both CRLF, both
//     reported unreadable in a map that was otherwise perfect.
//   - **Invalid UTF-8 is replaced the way Python's decoder replaces it**, which is one
//     U+FFFD per *maximal subpart* of an ill-formed sequence (Unicode's recommended
//     practice). Go's own conveniences disagree with it in both directions:
//     `strings.ToValidUTF8` folds a whole run of bad bytes into one replacement, and
//     `utf8.DecodeRune` gives one per byte, so `E2 82 41` would be one U+FFFD to Python
//     and two to a reader that trusted the latter. Written out, and pinned by
//     `tests/test_go_reader.py` against Python's decoder on a fixture of mixed bad bytes.

package main

import (
	"os"
	"strings"
)

// readSource reads a file as the host does. The one place this is done, because the
// parser and the hash must see the same text.
func readSource(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return normaliseNewlines(decodeReplacing(raw)), nil
}

func normaliseNewlines(s string) string {
	if !strings.Contains(s, "\r") {
		return s
	}
	return strings.ReplaceAll(strings.ReplaceAll(s, "\r\n", "\n"), "\r", "\n")
}

// decodeReplacing is Python's `bytes.decode("utf-8", errors="replace")`.
func decodeReplacing(b []byte) string {
	var out strings.Builder
	out.Grow(len(b))
	for i := 0; i < len(b); {
		c := b[i]
		if c < 0x80 {
			out.WriteByte(c)
			i++
			continue
		}
		// How many continuation bytes this lead byte wants, and the range the first of
		// them must fall in. The narrower first ranges are what exclude overlongs,
		// surrogates and code points above U+10FFFF.
		need, lo, hi := 0, byte(0x80), byte(0xBF)
		switch {
		case c >= 0xC2 && c <= 0xDF:
			need = 1
		case c == 0xE0:
			need, lo = 2, 0xA0
		case c >= 0xE1 && c <= 0xEC, c == 0xEE, c == 0xEF:
			need = 2
		case c == 0xED:
			need, hi = 2, 0x9F
		case c == 0xF0:
			need, lo = 3, 0x90
		case c >= 0xF1 && c <= 0xF3:
			need = 3
		case c == 0xF4:
			need, hi = 3, 0x8F
		default:
			// 0x80–0xC1 and 0xF5–0xFF never start a sequence: one replacement each.
			out.WriteString("�")
			i++
			continue
		}
		j := i + 1
		ok := true
		for k := 0; k < need; k++ {
			if j >= len(b) {
				ok = false
				break
			}
			first, last := byte(0x80), byte(0xBF)
			if k == 0 {
				first, last = lo, hi
			}
			if b[j] < first || b[j] > last {
				ok = false
				break
			}
			j++
		}
		if ok {
			out.Write(b[i:j])
		} else {
			// The lead byte and every valid continuation before the break are one
			// maximal subpart, and one replacement.
			out.WriteString("�")
		}
		i = j
	}
	return out.String()
}
