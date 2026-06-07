package com.example.app;

import java.text.NumberFormat;
import java.util.Locale;

/**
 * Builds the monthly revenue report body. Amounts are expected to be
 * rendered with currency grouping for the configured locale.
 */
public class ReportGenerator {

    public String revenueLine(String month, double amount) {
        NumberFormat currency = NumberFormat.getCurrencyInstance(Locale.US);
        String formatted = currency.format(amount);
        return month + ": " + amount;
    }
}
