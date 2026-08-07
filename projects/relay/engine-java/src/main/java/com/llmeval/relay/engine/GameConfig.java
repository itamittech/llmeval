package com.llmeval.relay.engine;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Function;

/**
 * Race settings.
 *
 * <p>{@link #anchor} is what escalation consults: null means the perfect anchor of an engine-only
 * run, while a harness passes a function over its real model. It receives the <em>public</em>
 * stage, so a harness cannot see the answer either — the same seam the {@link Runner} interface
 * is, one level down, and the reason this engine needs no model SDK.
 *
 * <p>The provenance fields are omitted from {@code game_started} when null, which is what keeps
 * the conformance vectors byte-stable while harnesses add their own metadata.
 */
public final class GameConfig {

    public int seed = 1;
    public int maxTurns = 60;
    public int stages = Track.TRACK_STAGES;
    public int escalationQuota = Game.ESCALATION_QUOTA;
    public int maxStalls = Game.MAX_STALLS;
    public int maxNoteChars = Game.MAX_NOTE_CHARS;
    public String ruleset = "baseline";
    public String stack = "none";
    public Map<String, Map<String, Object>> players = new LinkedHashMap<>();
    public Function<PublicStage, String> anchor;

    public String profile;
    public Map<String, Object> promptSet;
    public Map<String, Object> framework;
    public Map<String, Object> host;
    public Map<String, Object> anchorMeta;

    public GameConfig() {}

    public GameConfig(int seed, int maxTurns) {
        this.seed = seed;
        this.maxTurns = maxTurns;
    }
}
