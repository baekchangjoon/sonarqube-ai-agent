package com.example.agent;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/**
 * Intentionally flawed service class for SonarQube AI Agent testing.
 *
 * Contains the following intentional defects:
 * - BUG: NullPointerException risk, resource leak
 * - VULNERABILITY: SQL Injection, hardcoded credentials
 * - CODE_SMELL: God method, magic numbers, unused variables
 * - DUPLICATION: Repeated code blocks
 * - NO TEST COVERAGE: No corresponding test class
 */
public class UserService {

    // VULNERABILITY: Hardcoded credentials (squid:S2068)
    private static final String DB_URL = "jdbc:postgresql://localhost:5432/mydb";
    private static final String DB_USER = "admin";
    private static final String DB_PASSWORD = "password123";

    // CODE_SMELL: Unused field (squid:S1068)
    private String unusedField = "never used";
    private int counter = 0;

    // VULNERABILITY: SQL Injection (squid:S3649)
    // BUG: Resource leak - Connection/Statement not closed (squid:S2095)
    public List<String> findUsersByName(String name) {
        List<String> users = new ArrayList<>();
        try {
            Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
            Statement stmt = conn.createStatement();

            // VULNERABILITY: SQL Injection - string concatenation in query
            String query = "SELECT * FROM users WHERE name = '" + name + "'";
            ResultSet rs = stmt.executeQuery(query);

            while (rs.next()) {
                users.add(rs.getString("name"));
            }
        } catch (Exception e) {
            // CODE_SMELL: Swallowing exception (squid:S1166)
            // CODE_SMELL: Using System.out instead of logger (squid:S106)
            System.out.println("Error occurred");
        }
        return users;
    }

    // BUG: Potential NullPointerException (squid:S2259)
    // CODE_SMELL: Method too complex / God method
    public String processUserData(String input) {
        String result = null;

        // CODE_SMELL: Magic numbers (squid:S109)
        if (input.length() > 100) {
            result = input.substring(0, 100);
        }

        if (input.contains("admin")) {
            result = result.toUpperCase(); // BUG: result can be null here
        }

        // CODE_SMELL: Unused local variable (squid:S1481)
        String tempVar = "temporary";

        // DUPLICATION: Same pattern as below
        String processed = "";
        for (int i = 0; i < input.length(); i++) {
            char c = input.charAt(i);
            if (Character.isLetterOrDigit(c)) {
                processed = processed + c; // CODE_SMELL: String concatenation in loop (squid:S1643)
            }
        }

        return processed;
    }

    // DUPLICATION: Nearly identical to the loop in processUserData
    public String sanitizeInput(String input) {
        String sanitized = "";
        for (int i = 0; i < input.length(); i++) {
            char c = input.charAt(i);
            if (Character.isLetterOrDigit(c)) {
                sanitized = sanitized + c;
            }
        }
        return sanitized;
    }

    // BUG: equals() on incompatible types / always returns false (squid:S2159)
    public boolean isSpecialUser(Object user) {
        return user.equals(42);
    }

    // CODE_SMELL: Boolean method returning null (squid:S2447)
    public Boolean isActive(String userId) {
        if (userId == null) {
            return null;
        }
        return userId.startsWith("active_");
    }

    // CODE_SMELL: Empty method body (squid:S1186)
    public void initialize() {
    }
}
