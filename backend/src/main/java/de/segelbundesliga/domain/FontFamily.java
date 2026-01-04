package de.segelbundesliga.domain;

public enum FontFamily {
    HELVETICA("Helvetica"),
    ARIAL("Arial"),
    TIMES_NEW_ROMAN("Times New Roman");

    private final String displayName;

    FontFamily(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
