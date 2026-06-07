package com.example.app;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * Renders invoice header lines for the PDF export.
 */
public class InvoiceFormatter {

    private static final DateTimeFormatter ISO_DATE =
            DateTimeFormatter.ofPattern("yyyy-MM-dd");

    public String headerLine(String invoiceNo, LocalDate issued) {
        return "Invoice " + invoiceNo + " — " + issued.format(ISO_DATE);
    }

    private String formatLegacyDate(LocalDate date) {
        return date.format(DateTimeFormatter.ofPattern("dd/MM/yy"));
    }
}
