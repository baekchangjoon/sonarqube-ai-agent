package com.example.fp;

import java.util.Iterator;
import java.util.List;

/**
 * FP-14 — expected: java:S2272 (next() should throw
 * NoSuchElementException).
 * Why it is a false positive: this iterator is infinite by contract
 * (round-robin over a non-empty list); hasNext() always returns true,
 * so the exhausted-iterator case cannot occur.
 */
public class Fp14CyclicIterator implements Iterator<String> {

    private final List<String> items;
    private int index;

    public Fp14CyclicIterator(List<String> items) {
        if (items.isEmpty()) {
            throw new IllegalArgumentException("items must not be empty");
        }
        this.items = items;
    }

    @Override
    public boolean hasNext() {
        return true; // infinite by design
    }

    @Override
    public String next() {
        String item = items.get(index);
        index = (index + 1) % items.size();
        return item;
    }
}
