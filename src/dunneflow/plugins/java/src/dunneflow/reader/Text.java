package dunneflow.reader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * {@code ingest.contract.SOURCE_TEXT}: what "the text of a file" means, on both sides.
 *
 * <p>Python reads with {@code errors="replace"} and universal newlines. A CRLF file, or a
 * file with stray bytes, must therefore hash the same here as there, or it comes back
 * <i>changed while it was being read</i>.
 *
 * <p><b>The decoder is written by hand, and not taken from {@code CharsetDecoder}.</b>
 * Python replaces an ill-formed sequence once per <b>maximal subpart</b> (Unicode 3.9,
 * table 3-7). The JDK's decoder is not specified to do the same, and its behaviour is the
 * JDK's own: two machines on two JDKs could hash one file two ways, which is rule 66 in
 * the one value every cache key is built on. So the rule is spelt out here, once, and
 * {@code tests/fixtures/ids/vectors.json} is what says it agrees, rather than this comment.
 */
public final class Text {
    private Text() {}

    private static final char REPLACEMENT = '�';

    /** The bytes as Python's {@code bytes.decode("utf-8", "replace")} reads them. */
    public static String utf8Replace(byte[] b) {
        StringBuilder out = new StringBuilder(b.length);
        int i = 0;
        int n = b.length;
        while (i < n) {
            int c = b[i] & 0xff;
            if (c < 0x80) {
                out.append((char) c);
                i++;
                continue;
            }
            // How many continuation bytes this lead byte wants, and the range the first
            // continuation byte must fall in (table 3-7). Anything else is one bad byte.
            int need;
            int lo = 0x80;
            int hi = 0xbf;
            int cp;
            if (c >= 0xc2 && c <= 0xdf) {
                need = 1;
                cp = c & 0x1f;
            } else if (c >= 0xe0 && c <= 0xef) {
                need = 2;
                cp = c & 0x0f;
                if (c == 0xe0) {
                    lo = 0xa0;
                } else if (c == 0xed) {
                    hi = 0x9f;
                }
            } else if (c >= 0xf0 && c <= 0xf4) {
                need = 3;
                cp = c & 0x07;
                if (c == 0xf0) {
                    lo = 0x90;
                } else if (c == 0xf4) {
                    hi = 0x8f;
                }
            } else {
                out.append(REPLACEMENT);
                i++;
                continue;
            }
            int j = i + 1;
            boolean ok = true;
            for (int k = 0; k < need; k++, j++) {
                int lower = k == 0 ? lo : 0x80;
                int upper = k == 0 ? hi : 0xbf;
                if (j >= n || (b[j] & 0xff) < lower || (b[j] & 0xff) > upper) {
                    ok = false;
                    break;
                }
                cp = (cp << 6) | (b[j] & 0x3f);
            }
            if (ok) {
                out.appendCodePoint(cp);
                i = j;
            } else {
                // The maximal subpart is the lead byte plus every continuation byte that
                // was valid where it stood, and it is replaced once.
                out.append(REPLACEMENT);
                i = j;
            }
        }
        return out.toString();
    }

    /** Decoded, then CRLF and lone CR are each one {@code \n}, as universal newlines do. */
    public static String decode(byte[] raw) {
        String text = utf8Replace(raw);
        if (text.indexOf('\r') < 0) {
            return text;
        }
        return text.replace("\r\n", "\n").replace('\r', '\n');
    }

    public static String readSource(Path path) throws IOException {
        return decode(Files.readAllBytes(path));
    }
}
