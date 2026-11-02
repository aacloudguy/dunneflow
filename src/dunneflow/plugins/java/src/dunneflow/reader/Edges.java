package dunneflow.reader;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/**
 * Every call's far end, by javac. This is chunk 3 of the Java reader. Until then it answers
 * that it resolved nothing, which the host counts and says.
 */
public final class Edges {
    private Edges() {}

    public static final class Found {
        final List<Facts.SuppliedEdge> edges = new ArrayList<>();
        final List<String> notes = new ArrayList<>();
        long outside;
        long unknown;
    }

    static Found collect(Path root, List<Path> files, Rules rules, Function<Path, String> rel) {
        return new Found();
    }
}
