package com.example.core;

import java.lang.reflect.Field;
import java.util.StringJoiner;

/**
 * Wire payload for order submissions. Serialized field-by-field via
 * reflection by {@link #toJson()} (data-binding style), so fields and
 * JSON keys stay in lockstep.
 */
public class OrderPayload {

    private String orderId = "o-1";
    private int quantity = 2;
    private boolean express = false;

    public String toJson() throws ReflectiveOperationException {
        StringJoiner json = new StringJoiner(",", "{", "}");
        for (Field f : OrderPayload.class.getDeclaredFields()) {
            f.setAccessible(true);
            json.add("\"" + f.getName() + "\":\"" + f.get(this) + "\"");
        }
        return json.toString();
    }
}
