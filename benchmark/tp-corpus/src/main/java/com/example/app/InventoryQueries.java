package com.example.app;

/**
 * SQL statements for the inventory reporting endpoints. All three
 * statements read the same warehouse inventory table.
 */
public class InventoryQueries {

    public String countInStock() {
        return select("COUNT(*)", "warehouse_inventory", "qty > 0");
    }

    public String lowStockReport() {
        return select("sku, qty", "warehouse_inventory", "qty < 10");
    }

    public String valuationReport() {
        return select("SUM(qty * unit_cost)", "warehouse_inventory", null);
    }

    private String select(String columns, String table, String where) {
        String sql = "SELECT " + columns + " FROM " + table;
        return where == null ? sql : sql + " WHERE " + where;
    }
}
