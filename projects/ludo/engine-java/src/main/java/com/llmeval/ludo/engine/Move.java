package com.llmeval.ludo.engine;

/**
 * One legal move: which token, from where, to where.
 *
 * <p>{@code frm} rather than {@code from} because Python's {@code from} is a keyword — the name
 * is carried across so the two engines read alike, even though Java would allow {@code from}.
 *
 * <p>A {@code record} gives value equality and a hash code for free, which the engine relies on:
 * it validates an agent's choice with a set membership test.
 */
public record Move(int token, int frm, int to) {}
