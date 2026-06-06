package com.example.fp;

import java.util.Map;

/**
 * FP-12 — expected: java:S1192 (duplicated string literal).
 * Why it is a false positive: the "status" literals are semantically
 * distinct — a JSON field name, a database column, a UI label, and a
 * metric tag that merely share spelling today. One shared constant
 * would wrongly couple independent concepts that can diverge.
 */
public class Fp12DistinctLiterals {

    public void putJsonField(Map<String, Object> json, Object value) {
        json.put("status", value); // JSON wire field
    }

    public String sqlOrderBy() {
        return "ORDER BY " + "status"; // DB column
    }

    public String uiLabel() {
        return "status"; // screen label
    }

    public void tagMetric(Map<String, String> tags) {
        tags.put("status", "pending"); // metrics dimension
    }
}
