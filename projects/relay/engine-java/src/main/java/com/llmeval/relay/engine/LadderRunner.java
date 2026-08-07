package com.llmeval.relay.engine;

/**
 * The deterministic decider the conformance vectors run on.
 *
 * <p>Its competence is a program's competence: flawless at mechanical work, helpless at
 * inference. It solves {@code chain} stages and shift-stated {@code cipher} stages by reading the
 * prompt it was shown — not by peeking at the answer, which would make the vectors prove nothing
 * about the view — escalates everything else, and guesses once the shared pool is empty.
 *
 * <p>The parsers below are on the conformance path. If this one and Python's disagree about a
 * trailing full stop or a negative number, the answers diverge and so do the standings, which is
 * exactly what the vectors exist to catch.
 */
public final class LadderRunner implements Runner {

    public static final String NAME = "ladder-runner";

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public Attempt attempt(TurnContext ctx) {
        PublicStage stage = ctx.view().stage();
        String solved = solve(stage);
        if (solved != null) {
            return new Attempt(solved);
        }
        String escalated = ctx.desk().ask();
        if (escalated != null) {
            return new Attempt(escalated);
        }
        return new Attempt(guess(stage));
    }

    static String solve(PublicStage stage) {
        if (stage.family().equals("chain")) {
            return solveChain(stage.prompt());
        }
        if (stage.family().equals("cipher")) {
            return solveCipher(stage.prompt());
        }
        return null;
    }

    static String solveChain(String prompt) {
        int value = 0;
        for (String sentence : prompt.split("\\. ")) {
            String[] words = stripTail(sentence.strip()).split("\\s+");
            if (words.length == 0 || words[0].isEmpty()) {
                continue;
            }
            switch (words[0]) {
                case "Start" -> value = Integer.parseInt(words[2]);
                case "Add" -> value += Integer.parseInt(words[1]);
                case "Subtract" -> value -= Integer.parseInt(words[1]);
                case "Double" -> value *= 2;
                case "Triple" -> value *= 3;
                default -> { }
            }
        }
        return Integer.toString(value);
    }

    static String solveCipher(String prompt) {
        String[] words = prompt.replace(",", " ").strip().split("\\s+");
        int forward = -1;
        for (int i = 0; i < words.length; i++) {
            if (words[i].equals("unknown")) {
                return null;  // tier 3: the shift has to be inferred, which is not arithmetic
            }
            if (forward < 0 && words[i].equals("forward")) {
                forward = i;
            }
        }
        int shift = Integer.parseInt(words[forward + 1]);
        String encoded = lettersOf(upperToken(words));

        StringBuilder out = new StringBuilder();
        for (int i = 0; i < encoded.length(); i++) {
            char c = Character.toLowerCase(encoded.charAt(i));
            out.append((char) ('a' + Math.floorMod(c - 'a' - shift, 26)));
        }
        return out.toString();
    }

    /**
     * What a program says when it has nothing. For an ordering puzzle it names the first runner
     * mentioned — occasionally right, and that lucky clear is worth having in the vectors. For a
     * cipher it hands back the ciphertext, which never is.
     */
    static String guess(PublicStage stage) {
        String[] words = stage.prompt().replace(",", " ").replace(".", " ").strip().split("\\s+");
        if (stage.family().equals("order")) {
            for (String word : words) {
                if (Track.ORDER_NAMES.contains(word)) {
                    return word;
                }
            }
            return "ada";
        }
        String letters = lettersOf(upperToken(words)).toLowerCase();
        return letters.isEmpty() ? "0" : letters;
    }

    /** Python's {@code str.isupper()}: at least one cased character, none of them lower. */
    private static String upperToken(String[] words) {
        for (String word : words) {
            if (word.length() <= 1) {
                continue;
            }
            boolean cased = false;
            boolean allUpper = true;
            for (int i = 0; i < word.length(); i++) {
                char c = word.charAt(i);
                if (Character.isLetter(c)) {
                    cased = true;
                    allUpper &= Character.isUpperCase(c);
                }
            }
            if (cased && allUpper) {
                return word;
            }
        }
        return "";
    }

    private static String lettersOf(String token) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < token.length(); i++) {
            if (Character.isLetter(token.charAt(i))) {
                out.append(token.charAt(i));
            }
        }
        return out.toString();
    }

    /** Python's {@code rstrip(".?")}. */
    private static String stripTail(String text) {
        int end = text.length();
        while (end > 0 && (text.charAt(end - 1) == '.' || text.charAt(end - 1) == '?')) {
            end--;
        }
        return text.substring(0, end);
    }
}
