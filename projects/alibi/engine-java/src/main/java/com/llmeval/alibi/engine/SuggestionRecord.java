package com.llmeval.alibi.engine;

/**
 * What everyone at the table saw of one suggestion. The shown exhibit is deliberately absent —
 * only the suggester learned it.
 */
public record SuggestionRecord(int turn, Color player, String who, String how, String where,
                               String note, Color refuter) {}
