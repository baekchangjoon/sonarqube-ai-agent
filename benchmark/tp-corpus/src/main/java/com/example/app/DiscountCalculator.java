package com.example.app;

import java.util.List;

/**
 * Applies the loyalty discount to an order total. Loyalty members get
 * 5% off the item subtotal before shipping is added.
 */
public class DiscountCalculator {

    private static final double LOYALTY_RATE = 0.05;

    public double totalWithDiscount(List<Double> itemPrices,
                                    double shipping, boolean loyaltyMember) {
        double subtotal = itemPrices.stream()
                .mapToDouble(Double::doubleValue).sum();
        if (loyaltyMember) {
            subtotal = subtotal * (1.0 - LOYALTY_RATE);
        }
        subtotal = itemPrices.stream()
                .mapToDouble(Double::doubleValue).sum();
        return subtotal + shipping;
    }
}
