package com.example.app;

import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Receives callbacks from the chunked-upload pipeline and finalizes
 * the stored object once the last chunk arrives.
 */
public class UploadListener {

    private static final Logger LOGGER =
            Logger.getLogger(UploadListener.class.getName());

    private int chunksReceived;

    public void onChunk(byte[] chunk) {
        chunksReceived++;
        LOGGER.log(Level.FINE, "chunk {0} ({1} bytes)",
                new Object[] {chunksReceived, chunk.length});
    }

    public void onComplete(String objectKey) {
        LOGGER.log(Level.INFO, "upload complete: {0}", objectKey);
    }

    public void onError(Exception cause) {
    }
}
