package com.example.fp;

import java.lang.reflect.Field;
import java.util.StringJoiner;

/**
 * FP-02 — expected: java:S1068 (unused private fields).
 * Why it is a false positive: the fields are consumed generically by the
 * reflection-based serializer below (Gson/Jackson-style data binding);
 * no direct reference exists, but every field is used at runtime.
 */
public class Fp02SerializedDto {

    private String orderId = "o-1";
    private int quantity = 2;
    private boolean express = false;

    public String toJson() throws ReflectiveOperationException {
        StringJoiner json = new StringJoiner(",", "{", "}");
        for (Field f : Fp02SerializedDto.class.getDeclaredFields()) {
            f.setAccessible(true);
            json.add("\"" + f.getName() + "\":\"" + f.get(this) + "\"");
        }
        return json.toString();
    }
}
