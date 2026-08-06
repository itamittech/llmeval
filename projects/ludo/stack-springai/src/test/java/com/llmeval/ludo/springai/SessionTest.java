package com.llmeval.ludo.springai;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.ai.chat.messages.MessageType;
import org.springframework.ai.chat.model.ChatModel;

import com.llmeval.ludo.engine.Color;
import com.llmeval.ludo.engine.Decider;
import com.llmeval.ludo.engine.EventSink;
import com.llmeval.ludo.engine.FirstLegal;
import com.llmeval.ludo.engine.Game;
import com.llmeval.ludo.engine.GameConfig;
import com.llmeval.ludo.engine.Move;
import com.llmeval.ludo.engine.StateView;
import com.llmeval.ludo.engine.TurnContext;
import com.llmeval.ludo.engine.TurnEnd;
import com.llmeval.ludo.engine.TurnStart;

/**
 * Session persistence: agent-side state surviving the process — and the
 * asymmetry that is the capability-matrix finding. Two harnesses over one
 * directory stand in for two processes, mirroring the Strands stack's
 * test_session.py. The second test is the important one: conversations
 * survive with no save call at all, because the framework's JDBC repository
 * is the memory's actual backing store — while beliefs vanish without the
 * explicit save, because the framework never holds them.
 */
class SessionTest {

    private static final List<String> RED_TURN = List.of(
            "{\"token\": 0, \"to\": 0, \"reasoning\": \"out of base\"}",
            "{\"notes\": [{\"kind\": \"commitment\", \"about\": \"blue\", "
                    + "\"text\": \"promised not to capture me\"}]}");

    private static Harness build(Path dir, List<String> redScript) {
        Map<Color, ChatModel> models = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            models.put(color, new ScriptedChatModel(color == Color.RED ? redScript : List.of()));
        }
        return new Harness(ModelsConfig.load("dev"), Prompts.load(), models,
                new EventSink.ListSink(), 7, 0, 1, dir);
    }

    private static void playOneRedTurn(Harness harness) {
        StateView view = probeView();
        harness.deciders().get(Color.RED)
                .choose(new TurnContext(view, Color.RED, 6, List.of(new Move(0, -1, 0)), 1));
        harness.deciders().get(Color.RED)
                .reflect(new TurnEnd(view, Color.RED, 1, "moved", List.of()));
    }

    @Test
    void conversationAndBeliefsSurviveTheProcess(@TempDir Path dir) {
        Harness first = build(dir, RED_TURN);
        playOneRedTurn(first);
        first.persist();                     // what play() does in its finally

        // "Process two": a fresh harness over the same directory. There is no
        // load call to make — ChatMemory reads the repository, the repository
        // reads the database, and beliefs.json was read at construction.
        Harness second = build(dir, List.of());

        List<?> restored = second.conversation(Color.RED);
        assertEquals(4, restored.size());    // decide u/a + reflect u/a, in order
        assertEquals(MessageType.USER, second.conversation(Color.RED).get(0).getMessageType());
        assertTrue(second.conversation(Color.RED).get(3).getText().contains("promised"));
        assertTrue(second.memory(Color.RED).render(40).contains("promised not to capture me"));

        assertTrue(Files.exists(dir.resolve("conversations.mv.db")));   // H2: the file IS the database
        assertTrue(Files.exists(dir.resolve("beliefs.json")));          // ours: the framework has no place for it
    }

    @Test
    void conversationsWriteThroughButBeliefsNeedTheSave(@TempDir Path dir) {
        Harness first = build(dir, RED_TURN);
        playOneRedTurn(first);
        // no persist() — the process "died" before play()'s finally ran

        Harness second = build(dir, List.of());

        // The framework's half survived anyway: the advisor saved each
        // exchange through the JDBC repository as it happened. There is no
        // sync moment to forget — the Strands finding, inverted.
        assertEquals(4, second.conversation(Color.RED).size());
        // The harness's half is silently gone: reflect's note went into plain
        // Memory, which only persist() writes. The asymmetry IS the split.
        assertTrue(second.memory(Color.RED).notes().isEmpty());
    }

    private static StateView probeView() {
        // Same probe as HarnessTest: StateView's constructor is the engine's,
        // so capture one the way the engine hands them out.
        final StateView[] captured = new StateView[1];
        Game game = new Game(new GameConfig(1, 1), new EventSink.ListSink());
        game.play(Map.of(
                Color.RED, new Decider() {
                    public String name() { return "probe"; }
                    public Move choose(TurnContext ctx) {
                        captured[0] = ctx.state();
                        return ctx.legalMoves().get(0);
                    }
                    public void negotiate(TurnStart s) { captured[0] = s.state(); }
                },
                Color.GREEN, new FirstLegal(),
                Color.YELLOW, new FirstLegal(),
                Color.BLUE, new FirstLegal()));
        return captured[0];
    }
}
