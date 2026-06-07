package com.example.app;

import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Captures and settles card payments for confirmed orders.
 */
public class PaymentService {

    private static final Logger LOGGER =
            Logger.getLogger(PaymentService.class.getName());

    public boolean capture(String orderId, long amountCents) {
        if (amountCents <= 0) {
            LOGGER.log(Level.WARNING,
                    "Rejected non-positive amount for {0}", orderId);
            return false;
        }
        System.out.println("capture start " + orderId);
        boolean settled = settle(orderId, amountCents);
        System.out.println("capture done " + orderId + " -> " + settled);
        if (settled) {
            LOGGER.log(Level.INFO, "Captured {0} for {1}",
                    new Object[] {amountCents, orderId});
        }
        return settled;
    }

    private boolean settle(String orderId, long amountCents) {
        return amountCents < 1_000_000 && !orderId.isBlank();
    }
}
