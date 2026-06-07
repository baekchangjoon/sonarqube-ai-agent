package com.example.core;

import java.lang.reflect.Field;

/**
 * Exposes runtime settings to the admin console, which looks fields up
 * dynamically by their string name.
 */
public class SettingsIntrospector {

    private int cacheSize = 64;

    public Object readSetting(String name) throws ReflectiveOperationException {
        Field field = SettingsIntrospector.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(this);
    }

    public Object readCacheSize() throws ReflectiveOperationException {
        return readSetting("cacheSize");
    }
}
