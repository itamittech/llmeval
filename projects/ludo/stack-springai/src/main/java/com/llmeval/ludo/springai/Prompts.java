package com.llmeval.ludo.springai;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.yaml.snakeyaml.Yaml;

/**
 * Loads the shared prompt set — the Java half of the contract prompts.py keeps
 * in Python. Both must agree exactly: same validation, same literal
 * {@code {{name}}} rendering, same digest bytes, or the "identical prompts"
 * claim quietly stops being true.
 *
 * <p>No template logic, deliberately: two languages implementing conditionals
 * would disagree at the edges, and every disagreement would be an invisible
 * parity break (shared/prompts/README.md). Rendering is ten lines in either
 * language — that is the point.
 */
public final class Prompts {

    private static final Pattern VARIABLE = Pattern.compile("\\{\\{(\\w+)}}");
    private static final Pattern LOGIC =
            Pattern.compile("\\{\\{[#/^>!]|\\{%|\\$\\{|\\{\\{\\s*\\w+\\s*\\|");

    public record Template(String name, String text, List<String> variables) {

        /** Substitute every declared variable. Missing or extra ones are errors. */
        public String render(Map<String, Object> values) {
            Set<String> missing = new HashSet<>(variables);
            missing.removeAll(values.keySet());
            if (!missing.isEmpty()) {
                throw new IllegalArgumentException(name + ": missing " + missing);
            }
            Set<String> extra = new HashSet<>(values.keySet());
            variables.forEach(extra::remove);
            if (!extra.isEmpty()) {
                throw new IllegalArgumentException(name + ": undeclared " + extra);
            }
            String out = text;
            for (Map.Entry<String, Object> entry : values.entrySet()) {
                out = out.replace("{{" + entry.getKey() + "}}", String.valueOf(entry.getValue()));
            }
            return out;
        }
    }

    private final int version;
    private final String digest;
    private final List<Template> system;
    private final Map<String, Template> turn;

    private Prompts(int version, String digest, List<Template> system, Map<String, Template> turn) {
        this.version = version;
        this.digest = digest;
        this.system = system;
        this.turn = turn;
    }

    public int version() { return version; }

    /** {@code sha256:…} over the manifest and every template — same bytes as prompts.py. */
    public String digest() { return digest; }

    public Template turn(String name) {
        Template t = turn.get(name);
        if (t == null) throw new IllegalArgumentException("no turn template " + name);
        return t;
    }

    public Set<String> turnNames() { return turn.keySet(); }

    /** The cacheable layer: every {@code system/} template, concatenated in order. */
    public String systemPrompt(Map<String, Object> values) {
        List<String> parts = new ArrayList<>();
        for (Template t : system) {
            Map<String, Object> narrowed = new HashMap<>();
            for (String v : t.variables()) narrowed.put(v, values.get(v));
            parts.add(t.render(narrowed));
        }
        return String.join("\n\n", parts);
    }

    /** Walk up from the working directory to the repo root, where shared/ lives. */
    public static Path repoRoot() {
        Path here = Path.of("").toAbsolutePath();
        for (Path p = here; p != null; p = p.getParent()) {
            if (Files.exists(p.resolve("shared/prompts/ludo/manifest.yaml"))) return p;
        }
        throw new IllegalStateException("could not locate shared/prompts/ludo from " + here);
    }

    public static Prompts load() {
        return load(repoRoot().resolve("shared/prompts/ludo"));
    }

    @SuppressWarnings("unchecked")
    public static Prompts load(Path base) {
        try {
            Map<String, Object> manifest =
                    new Yaml().load(Files.readString(base.resolve("manifest.yaml"), StandardCharsets.UTF_8));
            int version = (int) manifest.get("version");

            List<Map<String, Object>> systemEntries = (List<Map<String, Object>>) manifest.get("system");
            Map<String, Map<String, Object>> turnEntries =
                    (Map<String, Map<String, Object>>) manifest.get("turn");

            List<Template> system = new ArrayList<>();
            for (Map<String, Object> entry : systemEntries) system.add(loadTemplate(base, entry));
            Map<String, Template> turn = new LinkedHashMap<>();
            turnEntries.forEach((name, entry) -> turn.put(name, loadTemplate(base, entry)));

            return new Prompts(version, digest(base, version, systemEntries, turnEntries), system, turn);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @SuppressWarnings("unchecked")
    private static Template loadTemplate(Path base, Map<String, Object> entry) {
        String file = (String) entry.get("file");
        String text;
        try {
            text = Files.readString(base.resolve(file), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        if (LOGIC.matcher(text).find()) {
            throw new IllegalStateException(file + ": template logic found — render it in code "
                    + "and pass the result in as one variable (shared/prompts/README.md)");
        }
        List<String> declared = entry.get("variables") == null
                ? List.of() : (List<String>) entry.get("variables");
        Set<String> used = new HashSet<>();
        Matcher m = VARIABLE.matcher(text);
        while (m.find()) used.add(m.group(1));
        if (!used.equals(new HashSet<>(declared))) {
            throw new IllegalStateException(file + ": manifest declares " + declared
                    + ", template uses " + used);
        }
        return new Template(file, text, declared);
    }

    /** Byte-for-byte the prompts.py algorithm: version, then each entry's file
     *  name and bytes, NUL-separated, manifest order. */
    private static String digest(Path base, int version, List<Map<String, Object>> system,
                                 Map<String, Map<String, Object>> turn) throws IOException {
        MessageDigest sha;
        try {
            sha = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
        sha.update(String.valueOf(version).getBytes(StandardCharsets.UTF_8));
        List<Map<String, Object>> entries = new ArrayList<>(system);
        entries.addAll(turn.values());
        for (Map<String, Object> entry : entries) {
            String file = (String) entry.get("file");
            sha.update(file.getBytes(StandardCharsets.UTF_8));
            sha.update((byte) 0);
            sha.update(Files.readAllBytes(base.resolve(file)));
            sha.update((byte) 0);
        }
        StringBuilder hex = new StringBuilder("sha256:");
        for (byte b : sha.digest()) hex.append(String.format("%02x", b));
        return hex.toString();
    }
}
