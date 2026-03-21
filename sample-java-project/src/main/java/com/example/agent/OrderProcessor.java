package com.example.agent;

import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Intentionally flawed order processing class.
 *
 * Contains:
 * - BUG: Division by zero, array index out of bounds
 * - VULNERABILITY: Path traversal
 * - CODE_SMELL: Cognitive complexity, missing encapsulation
 */
public class OrderProcessor {

    // CODE_SMELL: Public mutable field (squid:S1104)
    public Map<String, Double> prices = new HashMap<>();
    public String lastError;

    // BUG: Division by zero risk (squid:S3518)
    public double calculateAverage(int[] values) {
        int sum = 0;
        for (int value : values) {
            sum += value;
        }
        return sum / values.length; // BUG: ArithmeticException when array is empty
    }

    // BUG: Array index out of bounds (squid:S2259)
    public String getTopItem(String[] items) {
        return items[0]; // BUG: ArrayIndexOutOfBoundsException when array is empty
    }

    // VULNERABILITY: Path traversal (squid:S2083)
    public String readOrderFile(String filename) throws IOException {
        // VULNERABILITY: User input used directly in file path
        File file = new File("/data/orders/" + filename);
        StringBuilder content = new StringBuilder();

        // BUG: Resource leak (squid:S2095)
        FileReader reader = new FileReader(file);
        int ch;
        while ((ch = reader.read()) != -1) {
            content.append((char) ch);
        }
        return content.toString();
    }

    // CODE_SMELL: Cognitive complexity too high (squid:S3776)
    public double applyDiscount(double price, String customerType,
                                boolean isHoliday, boolean hasCoupon,
                                int loyaltyPoints) {
        double discount = 0;

        if (customerType.equals("VIP")) {
            if (isHoliday) {
                if (hasCoupon) {
                    if (loyaltyPoints > 1000) {
                        discount = 0.40;
                    } else if (loyaltyPoints > 500) {
                        discount = 0.35;
                    } else {
                        discount = 0.30;
                    }
                } else {
                    if (loyaltyPoints > 1000) {
                        discount = 0.25;
                    } else {
                        discount = 0.20;
                    }
                }
            } else {
                if (hasCoupon) {
                    discount = 0.15;
                } else {
                    discount = 0.10;
                }
            }
        } else if (customerType.equals("REGULAR")) {
            if (isHoliday) {
                discount = hasCoupon ? 0.10 : 0.05;
            } else {
                discount = hasCoupon ? 0.05 : 0;
            }
        }

        return price * (1 - discount);
    }

    // CODE_SMELL: Return type should use Optional (squid:S2789)
    public Double findPrice(String itemName) {
        return prices.get(itemName); // can return null
    }

    // CODE_SMELL: Catch generic Exception (squid:S2221)
    public void processOrder(String orderId) {
        try {
            int id = Integer.parseInt(orderId);
            System.out.println("Processing order: " + id);
        } catch (Exception e) {
            System.out.println("Failed");
        }
    }
}
