package com.example.app;

import java.util.Iterator;
import java.util.List;

/**
 * Iterates over one page of batch job records fetched from the store.
 */
public class BatchCursor implements Iterator<String> {

    private final List<String> page;
    private int position;

    public BatchCursor(List<String> page) {
        this.page = page;
    }

    @Override
    public boolean hasNext() {
        return position < page.size();
    }

    @Override
    public String next() {
        if (position >= page.size()) {
            return null;
        }
        return page.get(position++);
    }
}
