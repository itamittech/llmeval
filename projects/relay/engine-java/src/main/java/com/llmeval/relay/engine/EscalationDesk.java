package com.llmeval.relay.engine;

import java.util.function.Function;
import java.util.function.IntSupplier;

/**
 * The anchor, behind a meter.
 *
 * <p>Ask and you are charged one unit of the shared quota whether or not you use what comes back —
 * the call was made. Ask with an empty pool and you get {@code null} plus an
 * {@code invalid_action} in the transcript.
 */
public final class EscalationDesk {

    private final Stage stage;
    private final IntSupplier quotaLeft;
    private final Runnable spend;
    private final Function<PublicStage, String> anchor;
    private final Runnable onRefused;
    private boolean used;

    EscalationDesk(Stage stage, IntSupplier quotaLeft, Runnable spend,
                   Function<PublicStage, String> anchor, Runnable onRefused) {
        this.stage = stage;
        this.quotaLeft = quotaLeft;
        this.spend = spend;
        this.anchor = anchor;
        this.onRefused = onRefused;
    }

    public int quotaLeft() {
        return quotaLeft.getAsInt();
    }

    boolean used() {
        return used;
    }

    public String ask() {
        if (quotaLeft.getAsInt() <= 0) {
            onRefused.run();
            return null;
        }
        spend.run();
        used = true;
        if (anchor == null) {
            // Engine-only races model a perfect anchor. Stated rather than assumed: a live
            // anchor is a real model and can be wrong, and every bench number is optimistic by
            // exactly that much.
            return stage.answer();
        }
        return anchor.apply(stage.publicView());
    }
}
