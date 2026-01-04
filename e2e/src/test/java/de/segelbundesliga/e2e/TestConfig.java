package de.segelbundesliga.e2e;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.File;
import java.io.IOException;

/**
 * Test configuration loaded from YAML file or environment variables.
 */
public class TestConfig {

    private String testTarget = "http://localhost:3000";
    private String zitadelUrl = "http://localhost:8081";
    private String testUserName = "testuser";
    private String testUserPassword = "test1234";
    private Boolean headless = true;
    private String browser = "chromium";
    private Boolean useNullViewportSize = false;
    private Integer slowMoMs = 0;

    // Getters and Setters
    public String getTestTarget() { return testTarget; }
    public void setTestTarget(String testTarget) { this.testTarget = testTarget; }

    public String getZitadelUrl() { return zitadelUrl; }
    public void setZitadelUrl(String zitadelUrl) { this.zitadelUrl = zitadelUrl; }

    public String getTestUserName() { return testUserName; }
    public void setTestUserName(String testUserName) { this.testUserName = testUserName; }

    public String getTestUserPassword() { return testUserPassword; }
    public void setTestUserPassword(String testUserPassword) { this.testUserPassword = testUserPassword; }

    public Boolean getHeadless() { return headless; }
    public void setHeadless(Boolean headless) { this.headless = headless; }

    public String getBrowser() { return browser; }
    public void setBrowser(String browser) { this.browser = browser; }

    public Boolean getUseNullViewportSize() { return useNullViewportSize; }
    public void setUseNullViewportSize(Boolean useNullViewportSize) { this.useNullViewportSize = useNullViewportSize; }

    public Integer getSlowMoMs() { return slowMoMs; }
    public void setSlowMoMs(Integer slowMoMs) { this.slowMoMs = slowMoMs; }

    public static TestConfig loadConfig() {
        // First try environment variables
        TestConfig config = new TestConfig();

        String testTarget = System.getenv("SBL_TEST_TARGET");
        if (testTarget != null && !testTarget.isBlank()) {
            config.setTestTarget(testTarget);
        }

        String zitadelUrl = System.getenv("SBL_ZITADEL_URL");
        if (zitadelUrl != null && !zitadelUrl.isBlank()) {
            config.setZitadelUrl(zitadelUrl);
        }

        String testUser = System.getenv("SBL_TEST_USER");
        if (testUser != null && !testUser.isBlank()) {
            config.setTestUserName(testUser);
        }

        String testPassword = System.getenv("SBL_TEST_PASSWORD");
        if (testPassword != null && !testPassword.isBlank()) {
            config.setTestUserPassword(testPassword);
        }

        String headless = System.getProperty("headless");
        if (headless != null) {
            config.setHeadless(Boolean.parseBoolean(headless));
        }

        // Try loading from YAML config file
        String configFile = System.getProperty("testConfig");
        if (configFile != null && !configFile.isBlank()) {
            try {
                File file = new File(configFile);
                if (file.exists()) {
                    ObjectMapper mapper = new ObjectMapper(new YAMLFactory())
                            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
                    System.out.println("Loading test configuration from: " + configFile);
                    return mapper.readValue(file, TestConfig.class);
                }
            } catch (IOException e) {
                System.out.println("Failed to load config file: " + configFile + " - using defaults");
            }
        }

        return config;
    }
}
