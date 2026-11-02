package dunneflow.reader;

/**
 * {@code detectors/java.yaml}, as the host sends it in {@code open}.
 *
 * <p>The host loads and validates the rules file ({@code detectors.rules_document}). This
 * reader only reads the keys it acts on. A key it does not know is ignored, and a key it
 * does know in a shape it cannot read is a note on stderr and a rule read as empty, never
 * a guessed default (rule 49). Chunk 1 reads no rule yet. It keeps the document, so that
 * {@code open} can say when none arrived.
 */
public final class Rules {
    final Object raw;

    Rules(Object raw) {
        this.raw = raw;
    }

    int boundaryCount() {
        return Json.list(raw, "boundaries").size();
    }
}
