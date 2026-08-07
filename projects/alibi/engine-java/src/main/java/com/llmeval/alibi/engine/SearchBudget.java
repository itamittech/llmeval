package com.llmeval.alibi.engine;

import java.util.List;
import java.util.function.BiConsumer;

/**
 * The archive handle a detective deliberates through. Counts queries, reports to the game for
 * event emission, refuses politely when the turn's quota is spent — mirroring the Python
 * {@code SearchBudget} exactly, because quota behaviour is on the conformance path.
 */
public final class SearchBudget {

    private final Archive archive;
    private int quota;
    private final BiConsumer<String, List<Archive.Document>> onSearch;

    SearchBudget(Archive archive, int quota, BiConsumer<String, List<Archive.Document>> onSearch) {
        this.archive = archive;
        this.quota = quota;
        this.onSearch = onSearch;
    }

    public int quotaLeft() {
        return quota;
    }

    public List<Archive.Document> search(String query) {
        if (quota <= 0) {
            onSearch.accept(query, null); // emits invalid_action, not results
            return List.of();
        }
        quota--;
        List<Archive.Document> results = archive.search(query);
        onSearch.accept(query, results);
        return results;
    }
}
