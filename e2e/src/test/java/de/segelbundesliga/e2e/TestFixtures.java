package de.segelbundesliga.e2e;

import com.microsoft.playwright.Browser;
import com.microsoft.playwright.BrowserType;
import com.microsoft.playwright.Playwright;
import com.microsoft.playwright.options.ViewportSize;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Test fixtures and constants for E2E tests.
 */
public class TestFixtures {

    public static final TestConfig config = TestConfig.loadConfig();

    // Test System URLs
    public static final String TEST_TARGET = config.getTestTarget();
    public static final String ZITADEL_URL = config.getZitadelUrl();

    // Test User Credentials
    public static final String TEST_USER = config.getTestUserName();
    public static final String TEST_PASSWORD = config.getTestUserPassword();

    // Timing
    public static final int DELAY_IN_MS = config.getHeadless() ? 0 : 500;
    public static final int DEFAULT_TIMEOUT_IN_MS = 10_000;
    public static final int DEFAULT_NAVIGATION_TIMEOUT_IN_MS = 30_000;

    // Storage state for authenticated sessions
    public static final Path CONTEXT_STATE_PATH = Paths.get("./build/state.json");

    /**
     * Get the configured viewport size.
     */
    public static ViewportSize getViewportSize() {
        return config.getUseNullViewportSize() ? null : new ViewportSize(1280, 720);
    }

    /**
     * Launch a browser with the configured browser type.
     */
    public static Browser launchBrowser(Playwright playwright, BrowserType.LaunchOptions options) {
        String browser = config.getBrowser().toLowerCase();
        return switch (browser) {
            case "chromium" -> playwright.chromium().launch(options);
            case "firefox" -> playwright.firefox().launch(options);
            case "webkit" -> playwright.webkit().launch(options);
            default -> {
                System.out.println("Invalid browser: " + browser + " - using chromium");
                yield playwright.chromium().launch(options);
            }
        };
    }
}
