package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The archive: generated testimony, and the baseline retriever. Direct port of the Python
 * engine's {@code archive.py} — every template must render <em>byte for byte</em> identically,
 * because the conformance digest covers {@code archive_generated}. A stray comma here fails all
 * twenty vectors, which is the point.
 *
 * <p>Draw order is spec (see the Python module docstring); the retriever is integer-only so the
 * two languages cannot drift on ranking.
 */
public final class Archive {

    public static final int SEARCH_K = 3;

    static final List<String> WITNESSES = List.of(
            "head waiter Colin Pereira",
            "security guard Asha Nair",
            "pianist Leo Fernandes",
            "housekeeper Rekha Iyer",
            "bartender Sam Dutta",
            "florist Maria Gomes",
            "doorman Ravi Menon",
            "sous-chef Priya Nayak");

    static final List<String> NEUTRAL_SPOTS = List.of(
            "main stage", "reception desk", "front lawn", "buffet line");

    static final Map<String, String> METHOD_FACTS = Map.of(
            "sleight-of-hand",
            "the display case was fitted with a weight sensor, and it never tripped — nothing was lifted by hand",
            "duplicate-key",
            "the vault key never left the manager's chain, and the hourly key checks all passed",
            "service-hatch",
            "the service hatch was bolted and painted shut since the spring renovation",
            "blackout",
            "the generators kept every light burning all evening; there was no blackout",
            "forged-pass",
            "every pass scanned that night matched the printed guest register exactly");

    static final List<String> GOSSIP_TEMPLATES = List.of(
            "{witness} remarks: {suspect} seemed nervous all evening, checking the time again and again.",
            "{witness} recalls: {suspect} asked twice when the sapphire viewing would end.",
            "{witness} mentions: {suspect} and the auctioneer argued about money earlier in the week.",
            "{witness} says: {suspect} left the centenary toast early, glass still full.");

    private static final Pattern TOKEN = Pattern.compile("[a-z0-9]+");

    /** One archive entry. Only id/kind/text reach the transcript. */
    public record Document(String id, String kind, String text,
                           String assertsNot, boolean truthful, String witness) {

        public Map<String, Object> payload() {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("id", id);
            map.put("kind", kind);
            map.put("text", text);
            return map;
        }
    }

    private final List<Document> documents;
    private final Map<String, List<String>> docTokens = new LinkedHashMap<>();

    Archive(List<Document> documents) {
        this.documents = documents;
        for (Document doc : documents) {
            docTokens.put(doc.id(), tokens(doc.text()));
        }
    }

    public List<Document> documents() {
        return documents;
    }

    public List<String> redHerrings() {
        List<String> ids = new ArrayList<>();
        for (Document doc : documents) {
            if (!doc.truthful() && doc.assertsNot() != null) {
                ids.add(doc.id());
            }
        }
        return ids;
    }

    /** Deterministic keyword retrieval — integers only, mirroring the Python spec exactly. */
    public List<Document> search(String query, int k) {
        Set<String> want = new HashSet<>(tokens(query));
        record Hit(int score, int length, String id) {}
        List<Hit> hits = new ArrayList<>();
        for (Document doc : documents) {
            List<String> toks = docTokens.get(doc.id());
            Set<String> overlap = new HashSet<>(want);
            overlap.retainAll(new HashSet<>(toks));
            if (!overlap.isEmpty()) {
                hits.add(new Hit(overlap.size(), toks.size(), doc.id()));
            }
        }
        hits.sort(Comparator.comparingInt((Hit h) -> -h.score())
                .thenComparingInt(Hit::length)
                .thenComparing(Hit::id));
        List<Document> results = new ArrayList<>();
        for (Hit hit : hits.subList(0, Math.min(k, hits.size()))) {
            for (Document doc : documents) {
                if (doc.id().equals(hit.id())) {
                    results.add(doc);
                    break;
                }
            }
        }
        return results;
    }

    public List<Document> search(String query) {
        return search(query, SEARCH_K);
    }

    static List<String> tokens(String text) {
        List<String> out = new ArrayList<>();
        Matcher m = TOKEN.matcher(text.toLowerCase(Locale.ROOT));
        while (m.find()) {
            out.add(m.group());
        }
        return out;
    }

    // -- generation ------------------------------------------------------

    private record Row(String kind, String text, String assertsNot, boolean truthful, String witness) {}

    /** Kind and text for one exoneration — the template shared by truths and red herrings. */
    private static Row exoneration(String element, String witness, String spot, boolean truthful,
                                   boolean forceWitnessStatement) {
        String dim = CaseModel.dimensionOf(element);
        String kind;
        String text;
        if (dim.equals("who")) {
            kind = "witness_statement";
            text = witness + " states: " + CaseModel.DISPLAY.get(element)
                    + " never left the " + spot
                    + " between ten and midnight — half the room can confirm it.";
        } else if (dim.equals("how")) {
            kind = "forensic_note";
            text = witness + " confirms: " + METHOD_FACTS.get(element) + ".";
        } else {
            kind = "staff_log";
            text = witness + "'s log: " + CaseModel.DISPLAY.get(element)
                    + " was locked and under continuous watch from nine o'clock; nobody entered.";
        }
        if (forceWitnessStatement) {
            kind = "witness_statement";
        }
        return new Row(kind, text, element, truthful, witness);
    }

    public static Archive generate(CaseModel caseModel, Rng rng) {
        List<String> nonSolution = new ArrayList<>();
        for (String element : CaseModel.ALL_ELEMENTS) {
            if (!caseModel.solution().containsValue(element)) {
                nonSolution.add(element);
            }
        }
        List<String> exonerated = rng.sample(nonSolution, 8);
        exonerated.sort(Comparator.comparingInt(CaseModel.ALL_ELEMENTS::indexOf));

        List<String> pool = new ArrayList<>(WITNESSES);
        rng.shuffle(pool);
        List<String> liars = List.copyOf(pool.subList(0, 3));
        List<String> honest = List.copyOf(pool.subList(3, pool.size()));

        List<Row> rows = new ArrayList<>();

        for (int i = 0; i < exonerated.size(); i++) {
            String element = exonerated.get(i);
            String witness = honest.get(i % honest.size());
            String spot = CaseModel.dimensionOf(element).equals("who")
                    ? NEUTRAL_SPOTS.get(rng.below(NEUTRAL_SPOTS.size())) : null;
            rows.add(exoneration(element, witness, spot, true, false));
        }

        List<String> dims = List.of("who", "how", "where");
        for (int i = 0; i < dims.size(); i++) {
            String element = caseModel.solution().get(dims.get(i));
            String witness = liars.get(i);
            String spot = dims.get(i).equals("who")
                    ? NEUTRAL_SPOTS.get(rng.below(NEUTRAL_SPOTS.size())) : null;
            rows.add(exoneration(element, witness, spot, false, true));
        }

        for (int i = 0; i < liars.size(); i++) {
            String liar = liars.get(i);
            String counter = honest.get(i % honest.size());
            String text = counter + " notes: " + liar
                    + " left the gala before ten and spent the evening in the car park — whatever "
                    + liar + " says about that night is secondhand at best.";
            rows.add(new Row("staff_log", text, null, true, counter));
        }

        for (int i = 0; i < 6; i++) {
            String template = GOSSIP_TEMPLATES.get(rng.below(GOSSIP_TEMPLATES.size()));
            String suspect = CaseModel.WHO.get(rng.below(CaseModel.WHO.size()));
            String witness = honest.get(rng.below(honest.size()));
            String text = template
                    .replace("{witness}", witness)
                    .replace("{suspect}", CaseModel.DISPLAY.get(suspect));
            rows.add(new Row("gossip", text, null, true, witness));
        }

        rng.shuffle(rows);

        List<Document> documents = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            Row row = rows.get(i);
            documents.add(new Document(String.format("doc-%03d", i + 1), row.kind(), row.text(),
                    row.assertsNot(), row.truthful(), row.witness()));
        }
        // The ids in redHerrings() must come out ascending; assembly order guarantees it.
        Set<String> unique = new LinkedHashSet<>();
        for (Document doc : documents) {
            unique.add(doc.id());
        }
        if (unique.size() != documents.size()) {
            throw new IllegalStateException("duplicate document ids");
        }
        return new Archive(documents);
    }
}
