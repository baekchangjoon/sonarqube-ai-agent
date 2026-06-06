package com.example.fp;

import java.lang.reflect.Method;

/**
 * FP-13 — expected: java:S1144 (unused private method).
 * Why it is a false positive: the private method is dispatched by name
 * via reflection (plugin/handler registration by convention); static
 * analysis cannot trace string-based method lookups.
 */
public class Fp13ReflectiveMethod {

    private String handlePing(String payload) {
        return "pong:" + payload;
    }

    public Object dispatch(String handler, String payload)
            throws ReflectiveOperationException {
        Method method = Fp13ReflectiveMethod.class
                .getDeclaredMethod("handle" + handler, String.class);
        method.setAccessible(true);
        return method.invoke(this, payload);
    }
}
