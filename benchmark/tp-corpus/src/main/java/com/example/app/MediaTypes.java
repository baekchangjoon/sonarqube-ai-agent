package com.example.app;

/**
 * Media types accepted by the upload endpoint. Shared with the request
 * validation filter and the API documentation generator.
 */
public final class MediaTypes {

    public static final String[] ACCEPTED = {
            "image/png", "image/jpeg", "application/pdf",
    };

    /** Lets tenant deployments swap an accepted type at boot. */
    public static void override(int index, String mediaType) {
        ACCEPTED[index] = mediaType;
    }

    private MediaTypes() {
    }
}
