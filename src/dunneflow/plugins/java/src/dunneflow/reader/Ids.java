package dunneflow.reader;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Every id this reader mints, and the hash it echoes: {@code schema.py}'s, in Java.
 *
 * <p><b>Do not mint an id any other way</b> (LANGUAGES.md, rule 106). A definition is
 * {@code (file, qualname[, ordinal])} and a way in is {@code entrypoint_id(file, …)}, one
 * function each, for every reader. This is the fourth mirror of them, after
 * {@code ids.ts}, {@code ids.go} and {@code ids.rs}. It is pinned the same way, by
 * {@code tests/fixtures/ids/vectors.json}, which the host writes from {@code schema.py}
 * and {@link SelfTest} asserts.
 *
 * <p><b>BLAKE2b is written by hand</b>, because the JDK's {@code MessageDigest} has SHA-3
 * and no BLAKE2. The digest size is in the parameter block, so an 8-byte digest is
 * <b>not</b> a prefix of a 64-byte one. {@code make_id} joins its parts with NUL and hashes
 * them to 8 bytes; {@code hash_source} hashes to 16.
 */
public final class Ids {
    private Ids() {}

    private static final long[] IV = {
        0x6a09e667f3bcc908L, 0xbb67ae8584caa73bL, 0x3c6ef372fe94f82bL, 0xa54ff53a5f1d36f1L,
        0x510e527fade682d1L, 0x9b05688c2b3e6c1fL, 0x1f83d9abfb41bd6bL, 0x5be0cd19137e2179L,
    };

    private static final int[][] SIGMA = {
        {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15},
        {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3},
        {11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4},
        {7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8},
        {9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13},
        {2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9},
        {12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11},
        {13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10},
        {6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5},
        {10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0},
        {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15},
        {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3},
    };

    private static void g(long[] v, int a, int b, int c, int d, long x, long y) {
        v[a] = v[a] + v[b] + x;
        v[d] = Long.rotateRight(v[d] ^ v[a], 32);
        v[c] = v[c] + v[d];
        v[b] = Long.rotateRight(v[b] ^ v[c], 24);
        v[a] = v[a] + v[b] + y;
        v[d] = Long.rotateRight(v[d] ^ v[a], 16);
        v[c] = v[c] + v[d];
        v[b] = Long.rotateRight(v[b] ^ v[c], 63);
    }

    private static void compress(long[] h, byte[] block, long t, boolean last) {
        long[] m = new long[16];
        for (int i = 0; i < 16; i++) {
            long w = 0;
            for (int j = 7; j >= 0; j--) {
                w = (w << 8) | (block[i * 8 + j] & 0xffL);
            }
            m[i] = w;
        }
        long[] v = new long[16];
        System.arraycopy(h, 0, v, 0, 8);
        System.arraycopy(IV, 0, v, 8, 8);
        v[12] ^= t;
        if (last) {
            v[14] = ~v[14];
        }
        for (int[] s : SIGMA) {
            g(v, 0, 4, 8, 12, m[s[0]], m[s[1]]);
            g(v, 1, 5, 9, 13, m[s[2]], m[s[3]]);
            g(v, 2, 6, 10, 14, m[s[4]], m[s[5]]);
            g(v, 3, 7, 11, 15, m[s[6]], m[s[7]]);
            g(v, 0, 5, 10, 15, m[s[8]], m[s[9]]);
            g(v, 1, 6, 11, 12, m[s[10]], m[s[11]]);
            g(v, 2, 7, 8, 13, m[s[12]], m[s[13]]);
            g(v, 3, 4, 9, 14, m[s[14]], m[s[15]]);
        }
        for (int i = 0; i < 8; i++) {
            h[i] ^= v[i] ^ v[i + 8];
        }
    }

    static String blake2bHex(byte[] data, int outlen) {
        long[] h = IV.clone();
        h[0] ^= 0x01010000L ^ outlen;
        long t = 0;
        int off = 0;
        byte[] block = new byte[128];
        while (data.length - off > 128) {
            t += 128;
            System.arraycopy(data, off, block, 0, 128);
            compress(h, block, t, false);
            off += 128;
        }
        int rest = data.length - off;
        java.util.Arrays.fill(block, (byte) 0);
        System.arraycopy(data, off, block, 0, rest);
        t += rest;
        compress(h, block, t, true);
        StringBuilder out = new StringBuilder(outlen * 2);
        for (int i = 0; i < outlen; i++) {
            int b = (int) (h[i / 8] >>> (8 * (i % 8))) & 0xff;
            out.append(Character.forDigit(b >> 4, 16)).append(Character.forDigit(b & 0xf, 16));
        }
        return out.toString();
    }

    public static String makeId(List<String> parts) {
        return blake2bHex(String.join("\0", parts).getBytes(StandardCharsets.UTF_8), 8);
    }

    public static String makeId(String... parts) {
        return makeId(List.of(parts));
    }

    public static String definitionId(String file, String qualname, long ordinal) {
        return ordinal == 1 ? makeId(file, qualname) : makeId(file, qualname, "#" + ordinal);
    }

    public static String definitionId(String file, String qualname) {
        return definitionId(file, qualname, 1);
    }

    public static String entrypointId(String file, List<String> parts) {
        List<String> all = new ArrayList<>();
        all.add("ep");
        all.add(file);
        all.addAll(parts);
        return makeId(all);
    }

    public static String callSiteId(String callerId, String calleeExpr, long ordinal) {
        return makeId("site", callerId, calleeExpr, Long.toString(ordinal));
    }

    public static String controlPointId(String routineId, String kind, String header,
                                        long ordinal) {
        return makeId("control", routineId, kind, header, Long.toString(ordinal));
    }

    public static String hashSource(String text) {
        return blake2bHex(text.getBytes(StandardCharsets.UTF_8), 16);
    }
}
