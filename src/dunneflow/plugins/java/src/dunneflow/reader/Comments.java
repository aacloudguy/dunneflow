package dunneflow.reader;

import java.util.ArrayList;
import java.util.List;

/**
 * The comments javac's tree does not keep.
 *
 * <p>An ordinary comment is not a token, and it is gone by the time there is a tree. So
 * this is a scanner over the text. The only thing it has to get right is what is
 * <i>not</i> a comment: a {@code //} inside a string, a character literal or a text block
 * ({@code """…"""}). Block comments do not nest in Java, unlike Rust.
 *
 * <p><b>A Javadoc block is the declaration's docstring, and it is kept apart</b>, with its
 * offsets, so that it is recorded once. Recording it as a comment too would make one
 * sentence two facts (rule 40). {@code /**}{@code /} is an empty block comment and not
 * Javadoc, as javac reads it.
 */
final class Comments {
    private Comments() {}

    static final class Found {
        final String text;
        final long line;
        /** The comment stands on a line of its own. */
        final boolean leading;

        Found(String text, long line, boolean leading) {
            this.text = text;
            this.line = line;
            this.leading = leading;
        }
    }

    static final class Doc {
        /** Offsets into the text: the {@code /} that opens it and one past its {@code /}. */
        final int start;
        final int end;
        final String text;

        Doc(int start, int end, String text) {
            this.start = start;
            this.end = end;
            this.text = text;
        }
    }

    static final class Scan {
        final List<Found> comments = new ArrayList<>();
        final List<Doc> docs = new ArrayList<>();
    }

    static Scan scan(String s) {
        Scan out = new Scan();
        int n = s.length();
        int i = 0;
        long line = 1;
        int lineStart = 0;
        while (i < n) {
            char c = s.charAt(i);
            if (c == '\n') {
                line++;
                i++;
                lineStart = i;
            } else if (c == '/' && i + 1 < n && s.charAt(i + 1) == '/') {
                int end = s.indexOf('\n', i);
                end = end < 0 ? n : end;
                String text = s.substring(i + 2, end).strip();
                if (!text.isEmpty()) {
                    out.comments.add(new Found(text, line, s.substring(lineStart, i).isBlank()));
                }
                i = end;
            } else if (c == '/' && i + 1 < n && s.charAt(i + 1) == '*') {
                long startLine = line;
                boolean leading = s.substring(lineStart, i).isBlank();
                int begin = i;
                int close = s.indexOf("*/", i + 2);
                int end = close < 0 ? n : close + 2;
                for (int k = i; k < end; k++) {
                    if (s.charAt(k) == '\n') {
                        line++;
                        lineStart = k + 1;
                    }
                }
                String whole = s.substring(begin, end);
                String inner = whole.substring(2, Math.max(2, whole.length() - (close < 0 ? 0 : 2)));
                boolean doc = inner.startsWith("*") && !whole.equals("/**/");
                if (doc) {
                    String text = javadoc(inner.substring(1));
                    out.docs.add(new Doc(begin, end, text));
                } else {
                    String text = stripStars(inner);
                    if (!text.isEmpty()) {
                        out.comments.add(new Found(text, startLine, leading));
                    }
                }
                i = end;
            } else if (c == '"' && s.startsWith("\"\"\"", i)) {
                int close = s.indexOf("\"\"\"", i + 3);
                while (close > 0 && escaped(s, close)) {
                    close = s.indexOf("\"\"\"", close + 1);
                }
                int end = close < 0 ? n : close + 3;
                for (int k = i; k < end; k++) {
                    if (s.charAt(k) == '\n') {
                        line++;
                        lineStart = k + 1;
                    }
                }
                i = end;
            } else if (c == '"' || c == '\'') {
                i++;
                while (i < n && s.charAt(i) != c && s.charAt(i) != '\n') {
                    i += s.charAt(i) == '\\' ? 2 : 1;
                }
                i = Math.min(n, i + 1);
            } else {
                i++;
            }
        }
        return out;
    }

    /** Is the character at {@code at} preceded by an odd number of backslashes? */
    private static boolean escaped(String s, int at) {
        int k = at - 1;
        int count = 0;
        while (k >= 0 && s.charAt(k) == '\\') {
            count++;
            k--;
        }
        return count % 2 == 1;
    }

    /** A block comment's text, its leading {@code *} gutters removed. */
    private static String stripStars(String inner) {
        StringBuilder out = new StringBuilder();
        for (String l : inner.split("\n", -1)) {
            String t = l.strip();
            if (t.startsWith("*")) {
                t = t.substring(1).strip();
            }
            if (out.length() > 0) {
                out.append('\n');
            }
            out.append(t);
        }
        return out.toString().strip();
    }

    /** Javadoc as a reader reads it: the gutters gone, the tags kept as written. */
    static String javadoc(String inner) {
        return stripStars(inner);
    }
}
