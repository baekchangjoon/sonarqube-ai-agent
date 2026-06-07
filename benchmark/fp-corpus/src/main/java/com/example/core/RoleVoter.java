package com.example.core;

/**
 * One voter in the access-decision chain. Voters are polled in order;
 * a voter that has no opinion abstains and the next voter decides.
 */
public class RoleVoter {

    /** @return TRUE=allow, FALSE=deny, null=abstain (next voter decides) */
    public Boolean vote(String role) {
        if (role.startsWith("ADMIN")) {
            return Boolean.TRUE;
        }
        if (role.startsWith("BANNED")) {
            return Boolean.FALSE;
        }
        return null; // abstain: defer to the next voter in the chain
    }
}
