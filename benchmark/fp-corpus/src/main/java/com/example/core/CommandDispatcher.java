package com.example.core;

import java.lang.reflect.Method;

/**
 * Routes incoming commands to handler methods resolved by naming
 * convention: command "Ping" dispatches to {@code handlePing}. New
 * commands are added by declaring a matching handler method.
 */
public class CommandDispatcher {

    private String handlePing(String payload) {
        return "pong:" + payload;
    }

    public Object dispatch(String handler, String payload)
            throws ReflectiveOperationException {
        Method method = CommandDispatcher.class
                .getDeclaredMethod("handle" + handler, String.class);
        method.setAccessible(true);
        return method.invoke(this, payload);
    }
}
