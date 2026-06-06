package com.example.fp;

import java.util.Scanner;

/**
 * FP-07 — expected: java:S106 (System.out instead of logger).
 * Why it is a false positive: this is an INTERACTIVE console prompt —
 * the question must appear on the user's terminal, paired with reading
 * the answer from stdin. A logger writes to log sinks, not to the
 * interactive session; using one would break the dialog.
 */
public class Fp07ConsolePrompt {

    public String promptName() {
        Scanner scanner = new Scanner(System.in);
        System.out.print("name> ");
        return scanner.nextLine();
    }
}
