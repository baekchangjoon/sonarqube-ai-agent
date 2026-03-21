package com.example.agent;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Random;

/**
 * Intentionally flawed security utility class.
 *
 * Contains:
 * - VULNERABILITY: Weak cryptography, predictable random
 * - CODE_SMELL: Utility class design issues
 */
public class SecurityUtils {

    // CODE_SMELL: Utility class with public constructor (squid:S1118)

    // VULNERABILITY: Use of weak hash algorithm MD5 (squid:S4790)
    public static String hashPassword(String password) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(password.getBytes());
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            return password; // VULNERABILITY: Returning plaintext on failure
        }
    }

    // VULNERABILITY: Predictable random number generator (squid:S2245)
    public static String generateToken() {
        Random random = new Random();
        StringBuilder token = new StringBuilder();
        for (int i = 0; i < 32; i++) {
            token.append((char) ('a' + random.nextInt(26)));
        }
        return token.toString();
    }

    // VULNERABILITY: Hardcoded secret key (squid:S6418)
    public static boolean validateApiKey(String apiKey) {
        String secretKey = "sk-12345-abcde-secret-key";
        return secretKey.equals(apiKey);
    }

    // CODE_SMELL: Method with too many parameters (squid:S107)
    public static boolean checkAccess(String userId, String resource,
                                      String action, String ipAddress,
                                      String userAgent, String sessionId,
                                      String token, String role) {
        return userId != null && resource != null;
    }
}
