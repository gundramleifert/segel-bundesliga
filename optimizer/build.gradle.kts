plugins {
    id("java-library")
}

dependencies {
    // CLI parsing
    implementation("commons-cli:commons-cli:1.5.0")

    // YAML parsing (Jackson)
    implementation("com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.16.0")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.16.0")

    // PDF generation (iText)
    implementation("com.itextpdf:layout:7.2.5")
    implementation("com.itextpdf:kernel:7.2.5")

    // Logging
    implementation("org.slf4j:slf4j-api:2.0.9")
    runtimeOnly("ch.qos.logback:logback-classic:1.4.14")

    // Lombok
    compileOnly("org.projectlombok:lombok:1.18.30")
    annotationProcessor("org.projectlombok:lombok:1.18.30")

    // Testing
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.1")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
