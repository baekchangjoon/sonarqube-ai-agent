package com.example.core;

/**
 * Command-line entry point. Results are printed to stdout so they can
 * be piped into other tools ({@code wordcount file | sort}).
 */
public final class WordCountTool {

    private WordCountTool() {
    }

    public static void main(String[] args) {
        System.out.println("usage: wordcount <input>");
        if (args.length > 0) {
            System.out.println("result: " + args[0].length());
        }
    }
}
