package dunneflow.reader;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * The pins. {@code vectors.json} is the host's answer to every function in {@link Ids} and
 * to {@link Text#decode}, written from {@code schema.py} and from Python's own decoder by
 * {@code tools/gen_facts_go.py}.
 *
 * <p>There is no JUnit, because the reader takes no dependency it does not need. So this is
 * a mode of the reader itself ({@code --self-test <vectors.json>}), which pytest runs
 * through the jar the host built. The exit status is the number of disagreements, and each
 * one is named on stderr. A tampered vector was seen to fail before any was believed
 * (rule 59).
 */
final class SelfTest {
    private SelfTest() {}

    private static int failures;

    private static void check(String what, String got, String wanted) {
        if (!got.equals(wanted)) {
            failures++;
            Main.note("DISAGREES " + what + ": got " + got + ", wanted " + wanted);
        }
    }

    private static List<?> rows(Object v, String key) {
        List<?> rows = Json.list(v, key);
        if (rows.isEmpty()) {
            failures++;
            Main.note("DISAGREES " + key + ": no vectors at all, which checks nothing (rule 37)");
        }
        return rows;
    }

    private static String s(Object row, int i) {
        return (String) ((List<?>) row).get(i);
    }

    private static long n(Object row, int i) {
        return (Long) ((List<?>) row).get(i);
    }

    private static List<String> l(Object row, int i) {
        return Json.strings(((List<?>) row).get(i));
    }

    static int run(Path vectors) throws IOException {
        Object v = Json.parse(Files.readString(vectors, StandardCharsets.UTF_8));
        int rows = 0;
        for (Object r : rows(v, "make_id")) {
            check("make_id " + l(r, 0), Ids.makeId(l(r, 0)), s(r, 1));
            rows++;
        }
        for (Object r : rows(v, "definition_id")) {
            check("definition_id " + s(r, 1), Ids.definitionId(s(r, 0), s(r, 1), n(r, 2)), s(r, 3));
            rows++;
        }
        for (Object r : rows(v, "entrypoint_id")) {
            check("entrypoint_id " + l(r, 1), Ids.entrypointId(s(r, 0), l(r, 1)), s(r, 2));
            rows++;
        }
        for (Object r : rows(v, "call_site_id")) {
            check("call_site_id " + s(r, 1), Ids.callSiteId(s(r, 0), s(r, 1), n(r, 2)), s(r, 3));
            rows++;
        }
        for (Object r : rows(v, "control_point_id")) {
            check("control_point_id " + s(r, 1),
                Ids.controlPointId(s(r, 0), s(r, 1), s(r, 2), n(r, 3)), s(r, 4));
            rows++;
        }
        for (Object r : rows(v, "hash_source")) {
            check("hash_source", Ids.hashSource(s(r, 0)), s(r, 1));
            rows++;
        }
        for (Object r : rows(v, "decode")) {
            String hex = s(r, 0);
            byte[] bytes = new byte[hex.length() / 2];
            for (int i = 0; i < bytes.length; i++) {
                bytes[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
            }
            check("decode " + hex, escape(Text.decode(bytes)), escape(s(r, 1)));
            rows++;
        }
        Main.note(rows + " vectors, " + failures + " disagreeing");
        return failures;
    }

    private static String escape(String s) {
        StringBuilder out = new StringBuilder();
        Json.writeString(out, s);
        return out.toString();
    }
}
