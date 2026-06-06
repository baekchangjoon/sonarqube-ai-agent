package com.example.fp;

/**
 * FP-11 — expected: java:S2447 (null returned for Boolean).
 * Why it is a false positive: the documented API contract is tri-state —
 * TRUE (allowed), FALSE (denied), null (no decision; ask the next
 * voter). Callers are written against this contract (Spring Security
 * AccessDecisionVoter-style).
 */
public class Fp11TriState {

    /** @return TRUE=allow, FALSE=deny, null=abstain (next voter decides) */
    public Boolean vote(String role) {
        if (role.startsWith("ADMIN")) {
            return Boolean.TRUE;
        }
        if (role.startsWith("BANNED")) {
            return Boolean.FALSE;
        }
        return null; // abstain by contract
    }
}
