plugins {
    id("java")
}

dependencies {
    // Playwright
    testImplementation("com.microsoft.playwright:playwright:1.40.0")

    // JUnit 5
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.1")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")

    // AssertJ for fluent assertions
    testImplementation("org.assertj:assertj-core:3.24.2")

    // Jackson YAML for config loading
    testImplementation("com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.16.0")
    testImplementation("com.fasterxml.jackson.core:jackson-databind:2.16.0")

    // Lombok
    testCompileOnly("org.projectlombok:lombok:1.18.30")
    testAnnotationProcessor("org.projectlombok:lombok:1.18.30")

    // Logging (same versions as Spring Boot)
    testImplementation("org.slf4j:slf4j-api:2.0.9")
    testRuntimeOnly("ch.qos.logback:logback-classic:1.4.14")
}

tasks.test {
    useJUnitPlatform()

    // E2E tests should run sequentially
    maxParallelForks = 1

    // Pass system properties for configuration
    systemProperty("app.baseUrl", System.getProperty("app.baseUrl", "http://localhost:3000"))
    systemProperty("zitadel.url", System.getProperty("zitadel.url", "http://localhost:8081"))
    systemProperty("headless", System.getProperty("headless", "true"))

    testLogging {
        events("passed", "skipped", "failed")
        showStandardStreams = true
    }
}

// Task to install Playwright browsers
tasks.register<Exec>("installBrowsers") {
    commandLine("npx", "playwright", "install", "chromium")
    doFirst {
        println("Installing Playwright browsers...")
    }
}
