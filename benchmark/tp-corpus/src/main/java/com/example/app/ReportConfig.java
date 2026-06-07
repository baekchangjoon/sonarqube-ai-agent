package com.example.app;

/**
 * Options controlling a single report export run.
 */
public class ReportConfig {

    private final String title;
    private final String format;
    private final String locale;
    private final String timezone;
    private final boolean includeCharts;
    private final boolean includeRawData;
    private final int pageSize;
    private final int maxRows;

    public ReportConfig(String title, String format, String locale,
                        String timezone, boolean includeCharts,
                        boolean includeRawData, int pageSize, int maxRows) {
        this.title = title;
        this.format = format;
        this.locale = locale;
        this.timezone = timezone;
        this.includeCharts = includeCharts;
        this.includeRawData = includeRawData;
        this.pageSize = pageSize;
        this.maxRows = maxRows;
    }

    public String summary() {
        return title + " (" + format + ", " + locale + ", " + timezone
                + ", charts=" + includeCharts + ", raw=" + includeRawData
                + ", page=" + pageSize + ", max=" + maxRows + ")";
    }
}
