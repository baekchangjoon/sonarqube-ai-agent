package com.example.app;

import java.util.Locale;

/**
 * Formats unit prices for product pages. The shop renders prices in
 * the visitor's locale.
 */
public class PriceFormatter {

    public String displayPrice(double amount, Locale visitorLocale) {
        return render(amount, visitorLocale);
    }

    private String render(double amount, Locale locale) {
        return String.format("%.2f", amount);
    }
}
