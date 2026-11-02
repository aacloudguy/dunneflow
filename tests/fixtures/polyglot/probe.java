// Java's seventh of the probe tree: a way in, a boundary, a loop and a branch.

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

class Probe {
    static final int RETRIES = 3;

    /** One line of a config file. */
    record Setting(String key, String value) {}

    /** Reads a config file, one line at a time. */
    static List<Setting> loadConfig(String path) {
        List<Setting> out = new ArrayList<>();
        List<String> lines;
        try {
            lines = Files.readAllLines(Path.of(path));
        } catch (IOException e) {
            return out;
        }
        for (String line : lines) {
            int eq = line.indexOf('=');
            if (eq > 0) {
                out.add(new Setting(line.substring(0, eq).trim(), line.substring(eq + 1).trim()));
            }
        }
        return out;
    }

    static String root() {
        String r = System.getenv("PROBE_ROOT");
        return r == null || r.isEmpty() ? "." : r;
    }

    public static void main(String[] args) {
        List<Setting> settings = loadConfig(root() + "/probe.cfg");
        System.out.println(settings.size() + " settings, " + RETRIES + " retries");
    }
}
