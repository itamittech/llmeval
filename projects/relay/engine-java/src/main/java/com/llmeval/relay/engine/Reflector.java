package com.llmeval.relay.engine;

/** Optional. Called once per own turn, after it resolves. */
public interface Reflector {

    void reflect(TurnEnd end);
}
