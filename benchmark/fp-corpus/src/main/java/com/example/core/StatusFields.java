package com.example.core;

import java.util.Map;

/**
 * Adapters between the order model and its external representations:
 * the JSON wire format, the reporting SQL, the UI, and the metrics
 * pipeline. Each representation owns its own field naming.
 */
public class StatusFields {

    public void putJsonField(Map<String, Object> json, Object value) {
        json.put("status", value); // JSON wire field (API contract)
    }

    public String sqlOrderBy() {
        return "ORDER BY " + "status"; // DB column (schema-owned)
    }

    public String uiLabel() {
        return "status"; // screen label (copy text, may be localized)
    }

    public void tagMetric(Map<String, String> tags) {
        tags.put("status", "pending"); // metrics dimension (dashboard-owned)
    }
}
