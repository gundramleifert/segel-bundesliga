package de.segelbundesliga.e2e;

import com.microsoft.playwright.*;
import com.microsoft.playwright.options.AriaRole;
import com.microsoft.playwright.options.WaitForSelectorState;
import org.junit.jupiter.api.*;

import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Base class for E2E tests with Playwright.
 * Handles browser lifecycle and authentication.
 */
public abstract class BaseE2ETest {

    protected static final String BASE_URL = System.getProperty("app.baseUrl", "http://localhost:3000");
    protected static final String ZITADEL_URL = System.getProperty("zitadel.url", "http://localhost:8081");
    protected static final boolean HEADLESS = Boolean.parseBoolean(System.getProperty("headless", "true"));

    // Test user credentials (created by setup_test_users.py)
    protected static final String TEST_USER = "testuser";
    protected static final String TEST_PASSWORD = "Test1234";

    // Shared browser instance
    protected static Playwright playwright;
    protected static Browser browser;

    // Per-test context and page
    protected BrowserContext context;
    protected Page page;

    // Path to store authenticated state
    private static final Path AUTH_STATE_PATH = Paths.get("target", "auth-state.json");

    @BeforeAll
    static void setupBrowser() {
        playwright = Playwright.create();
        browser = playwright.chromium().launch(new BrowserType.LaunchOptions()
                .setHeadless(HEADLESS)
                .setSlowMo(HEADLESS ? 0 : 100)); // Slow down for visibility in headed mode
    }

    @AfterAll
    static void teardownBrowser() {
        if (browser != null) {
            browser.close();
        }
        if (playwright != null) {
            playwright.close();
        }
    }

    @BeforeEach
    void setupContext() {
        context = browser.newContext(new Browser.NewContextOptions()
                .setViewportSize(1280, 720));
        page = context.newPage();
    }

    @AfterEach
    void teardownContext() {
        if (context != null) {
            context.close();
        }
    }

    /**
     * Navigate to a path relative to the base URL.
     */
    protected void navigateTo(String path) {
        page.navigate(BASE_URL + path);
    }

    /**
     * Perform login via Zitadel UI.
     * This method handles the full OIDC flow.
     */
    protected void login() {
        login(TEST_USER, TEST_PASSWORD);
    }

    /**
     * Perform login with specific credentials.
     * Simplified for test user with pre-verified email and no MFA.
     */
    protected void login(String username, String password) {
        // Navigate to app and click login
        navigateTo("/");
        page.waitForLoadState();
        System.out.println("App loaded: " + page.url());

        // Wait for login button to be visible
        Locator loginBtn = page.getByTestId("login-button");
        loginBtn.waitFor(new Locator.WaitForOptions()
                .setState(WaitForSelectorState.VISIBLE)
                .setTimeout(10000));
        System.out.println("Login button visible, clicking...");
        loginBtn.click();

        // Wait a moment and check what happened
        page.waitForTimeout(3000);
        System.out.println("After click, URL: " + page.url());

        // If not redirected, take screenshot
        if (!page.url().contains("localhost:8081")) {
            page.screenshot(new Page.ScreenshotOptions()
                    .setPath(Paths.get("build", "after-login-click.png")));
            System.out.println("Screenshot saved - not redirected to Zitadel");
        }

        // Wait for Zitadel login page
        page.waitForURL(url -> url.contains("localhost:8081"), new Page.WaitForURLOptions()
                .setTimeout(30000));
        page.waitForLoadState();
        System.out.println("On Zitadel login page: " + page.url());

        // Wait for login form to be ready
        page.waitForTimeout(3000);
        System.out.println("Zitadel page loaded, URL: " + page.url());

        // Take screenshot to see what Zitadel shows
        page.screenshot(new Page.ScreenshotOptions()
                .setPath(Paths.get("build", "zitadel-page.png")));

        // Enter username using standard click() instead of dispatchEvent
        Locator loginName = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Login Name"));
        loginName.click();
        loginName.fill(username);
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Next")).click();

        // Wait for password page to load
        page.waitForTimeout(1000);
        System.out.println("After username submit: " + page.url());

        // Enter password
        Locator loginPassword = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Password"));
        loginPassword.waitFor(new Locator.WaitForOptions()
                .setState(WaitForSelectorState.VISIBLE)
                .setTimeout(10000));
        loginPassword.click();
        loginPassword.fill(password);

        // Wait for button to become enabled after filling password
        page.waitForTimeout(500);

        // Take screenshot before submit
        page.screenshot(new Page.ScreenshotOptions()
                .setPath(Paths.get("build", "before-submit.png")));
        System.out.println("Screenshot saved before submit");

        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Next")).click();
        page.waitForTimeout(2000);

        System.out.println("After password submit: " + page.url());
        System.out.println("Page title: " + page.title());

        // Handle 2-Factor Setup if it appears
        if (page.title().equals("2-Factor Setup")) {
            Locator skipButton = page.getByRole(AriaRole.BUTTON,
                    new Page.GetByRoleOptions().setName("Skip"));
            if (skipButton.isVisible()) {
                skipButton.dispatchEvent("click");
            }
        }

        // Take screenshot after submit
        page.screenshot(new Page.ScreenshotOptions()
                .setPath(Paths.get("build", "after-submit.png")));
        System.out.println("Screenshot saved after submit");

        // Wait for redirect back to app
        page.waitForURL(url -> url.startsWith(BASE_URL), new Page.WaitForURLOptions()
                .setTimeout(30000));
        page.waitForLoadState();

        // Verify we're logged in
        page.getByTestId("user-name").waitFor(new Locator.WaitForOptions()
                .setState(WaitForSelectorState.VISIBLE)
                .setTimeout(10000));
    }

    /**
     * Check if currently logged in.
     */
    protected boolean isLoggedIn() {
        return page.getByTestId("user-name").isVisible();
    }

    /**
     * Perform logout.
     */
    protected void logout() {
        if (isLoggedIn()) {
            // Click on avatar to open dropdown menu
            page.getByTestId("user-menu-button").click();
            page.waitForTimeout(300);
            // Then click logout button in dropdown
            page.getByTestId("logout-button").click();
            // Wait for login button to appear
            page.getByTestId("login-button").waitFor(new Locator.WaitForOptions()
                    .setState(WaitForSelectorState.VISIBLE)
                    .setTimeout(10000));
        }
    }

    /**
     * Wait for an element with a test ID to be visible.
     */
    protected Locator waitForTestId(String testId) {
        Locator locator = page.getByTestId(testId);
        locator.waitFor(new Locator.WaitForOptions()
                .setState(WaitForSelectorState.VISIBLE)
                .setTimeout(10000));
        return locator;
    }

    /**
     * Click an element by test ID.
     */
    protected void clickTestId(String testId) {
        page.getByTestId(testId).click();
    }

    /**
     * Fill an input by test ID.
     */
    protected void fillTestId(String testId, String value) {
        page.getByTestId(testId).fill(value);
    }

    /**
     * Get text content of element by test ID.
     */
    protected String getTextByTestId(String testId) {
        return page.getByTestId(testId).textContent();
    }
}
