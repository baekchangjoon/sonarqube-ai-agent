package com.example.core;

import java.util.Scanner;

/**
 * Interactive terminal dialog used by the setup wizard: prints a
 * question to the user's terminal and reads the answer from stdin.
 */
public class InteractivePrompt {

    public String promptName() {
        Scanner scanner = new Scanner(System.in);
        System.out.print("name> ");
        return scanner.nextLine();
    }
}
