package com.example.agent;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Minimal test class — intentionally low coverage.
 * AI Agent should generate additional tests to improve coverage.
 */
class OrderProcessorTest {

    @Test
    void testApplyDiscountForRegularCustomer() {
        OrderProcessor processor = new OrderProcessor();
        double result = processor.applyDiscount(100.0, "REGULAR", false, false, 0);
        assertEquals(100.0, result, 0.01);
    }
}
