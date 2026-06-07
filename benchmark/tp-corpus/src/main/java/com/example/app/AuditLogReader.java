package com.example.app;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

/**
 * Fetches recent audit trail entries for the admin console.
 */
public class AuditLogReader {

    private final OrderRepository repository;

    public AuditLogReader(OrderRepository repository) {
        this.repository = repository;
    }

    public List<String> recentEntries(int limit) throws SQLException {
        List<String> entries = new ArrayList<>();
        Connection conn = repository.openConnection();
        PreparedStatement stmt = conn.prepareStatement(
                "SELECT entry FROM audit_log ORDER BY at DESC LIMIT ?");
        stmt.setInt(1, limit);
        ResultSet rs = stmt.executeQuery();
        while (rs.next()) {
            entries.add(rs.getString("entry"));
        }
        return entries;
    }
}
