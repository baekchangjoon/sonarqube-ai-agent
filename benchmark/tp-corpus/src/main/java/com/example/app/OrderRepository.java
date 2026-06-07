package com.example.app;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/**
 * Read/write access to the orders schema on the primary database.
 */
public class OrderRepository {

    private static final String JDBC_URL =
            "jdbc:postgresql://db-primary.internal.example.com:5432/orders";
    private static final String DB_USER = "orders_rw";
    private static final String DB_PASSWORD = "Xk9#mQ2vL5pT";

    public Connection openConnection() throws SQLException {
        return DriverManager.getConnection(JDBC_URL, DB_USER, DB_PASSWORD);
    }
}
