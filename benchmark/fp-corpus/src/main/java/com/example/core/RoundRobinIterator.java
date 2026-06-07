package com.example.core;

import java.util.Iterator;
import java.util.List;

/**
 * Cycles forever over a non-empty list of upstream endpoints — the
 * load balancer calls {@code next()} once per request, indefinitely.
 */
public class RoundRobinIterator implements Iterator<String> {

    private final List<String> items;
    private int index;

    public RoundRobinIterator(List<String> items) {
        if (items.isEmpty()) {
            throw new IllegalArgumentException("items must not be empty");
        }
        this.items = items;
    }

    @Override
    public boolean hasNext() {
        return true; // a round-robin cycle has no end
    }

    @Override
    public String next() {
        String item = items.get(index);
        index = (index + 1) % items.size();
        return item;
    }
}
