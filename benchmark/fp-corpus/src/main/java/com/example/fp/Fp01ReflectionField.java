package com.example.fp;

import java.lang.reflect.Field;

/**
 * FP-01 — expected: java:S1068 (unused private field).
 * Why it is a false positive: the field is read by name via reflection;
 * static analysis cannot trace string-based field lookups.
 */
public class Fp01ReflectionField {

    private int cacheSize = 64;

    public Object readSetting(String name) throws ReflectiveOperationException {
        Field field = Fp01ReflectionField.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(this);
    }

    public Object readCacheSize() throws ReflectiveOperationException {
        return readSetting("cacheSize");
    }
}
