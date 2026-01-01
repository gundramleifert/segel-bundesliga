package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;

import com.microsoft.playwright.*;
import com.microsoft.playwright.options.AriaRole;
import com.microsoft.playwright.options.WaitForSelectorState;
import org.junit.jupiter.api.*;

import java.nio.file.Paths;

/**
 * Unified base class for all E2E tests.
 *
 * Features:
 * - Thread-safe Playwright management via PlaywrightThreadFactory
 * - Storage state reuse for authenticated sessions
 * - Consistent helper methods for common operations
 * - German UI support for Zitadel login
 */
public abstract class E2ETestBase {

    protected Page page;

    /**
     * Override this to specify if the test needs authentication.
     * Default is true (most tests need login).
     */
    protected boolean requiresAuthentication() {
        return true;
    }

    @BeforeEach
    void setUp() {
        // Try to reuse existing login state if authentication is required
        page = PlaywrightThreadFactory.getPage(requiresAuthentication());

        if (requiresAuthentication() && !isLoggedIn()) {
            performLogin();
        }
    }

    @AfterEach
    void tearDown() {
        PlaywrightThreadFactory.closePage();
    }

    // ==================== Navigation ====================

    /**
     * Navigate to a path relative to the base URL.
     */
    protected void navigateTo(String path) {
        String url = path.startsWith("http") ? path : TEST_TARGET + path;
        page.navigate(url);
        page.waitForLoadState();
    }

    // ==================== Authentication ====================

    /**
     * Check if user is currently logged in.
     */
    protected boolean isLoggedIn() {
        try {
            return page.getByTestId("user-menu-button").isVisible();
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Perform login via Zitadel.
     * Handles German UI labels.
     */
    protected void performLogin() {
        performLogin(TEST_USER, TEST_PASSWORD);
    }

    /**
     * Perform login with specific credentials.
     */
    protected void performLogin(String username, String password) {
        navigateTo("/");
        page.waitForTimeout(2000); // Wait for auth state to settle

        // Check if already logged in
        if (isLoggedIn()) {
            return; // Already logged in, nothing to do
        }

        // Click login button
        Locator loginButton = page.getByTestId("login-button");
        loginButton.waitFor(new Locator.WaitForOptions().setTimeout(DEFAULT_TIMEOUT_IN_MS));
        loginButton.click();

        // Wait for Zitadel
        page.waitForURL(url -> url.contains("localhost:8081"),
                new Page.WaitForURLOptions().setTimeout(DEFAULT_NAVIGATION_TIMEOUT_IN_MS));
        page.waitForLoadState();
        page.waitForTimeout(2000);

        // Enter username (German: "Loginname")
        Locator loginName = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Loginname"));
        loginName.waitFor(new Locator.WaitForOptions().setTimeout(DEFAULT_TIMEOUT_IN_MS));
        loginName.click();
        loginName.fill(username);

        // Click "Weiter" (German for "Next")
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter")).click();
        page.waitForTimeout(2000);

        // Enter password (German: "Passwort")
        Locator loginPassword = page.getByRole(AriaRole.TEXTBOX,
                new Page.GetByRoleOptions().setName("Passwort"));
        loginPassword.waitFor(new Locator.WaitForOptions().setTimeout(DEFAULT_TIMEOUT_IN_MS));
        loginPassword.click();
        loginPassword.fill(password);

        // Submit
        page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Weiter")).click();
        page.waitForTimeout(3000);

        // Handle 2-Factor Setup if it appears
        String title = page.title();
        if (title.contains("2-Faktor") || title.contains("2-Factor")) {
            Locator skipButton = page.getByRole(AriaRole.BUTTON,
                    new Page.GetByRoleOptions().setName("Überspringen"));
            if (!skipButton.isVisible()) {
                skipButton = page.getByRole(AriaRole.BUTTON,
                        new Page.GetByRoleOptions().setName("Skip"));
            }
            if (skipButton.isVisible()) {
                skipButton.dispatchEvent("click");
            }
        }

        // Wait for redirect back to app
        page.waitForURL(url -> url.startsWith(TEST_TARGET),
                new Page.WaitForURLOptions().setTimeout(DEFAULT_NAVIGATION_TIMEOUT_IN_MS));

        // Wait for page to fully load and auth state to settle
        page.waitForLoadState();
        page.waitForTimeout(3000);

        // Save storage state for reuse
        PlaywrightThreadFactory.saveStorageState();
    }

    /**
     * Perform logout.
     */
    protected void performLogout() {
        if (isLoggedIn()) {
            page.getByTestId("user-menu-button").click();
            page.waitForTimeout(300);
            page.getByTestId("logout-button").click();
            page.getByTestId("login-button").waitFor(
                    new Locator.WaitForOptions()
                            .setState(WaitForSelectorState.VISIBLE)
                            .setTimeout(DEFAULT_TIMEOUT_IN_MS));
        }
    }

    // ==================== Element Helpers ====================

    /**
     * Wait for an element with test ID to be visible.
     */
    protected Locator waitForTestId(String testId) {
        return waitForTestId(testId, DEFAULT_TIMEOUT_IN_MS);
    }

    /**
     * Wait for an element with test ID to be visible with custom timeout.
     */
    protected Locator waitForTestId(String testId, int timeoutMs) {
        Locator locator = page.getByTestId(testId);
        locator.waitFor(new Locator.WaitForOptions()
                .setState(WaitForSelectorState.VISIBLE)
                .setTimeout(timeoutMs));
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
     * Get text content by test ID.
     */
    protected String getTextByTestId(String testId) {
        return page.getByTestId(testId).textContent();
    }

    /**
     * Check if element with test ID exists.
     */
    protected boolean hasTestId(String testId) {
        return page.getByTestId(testId).count() > 0;
    }

    /**
     * Check if element with test ID is visible.
     */
    protected boolean isVisibleTestId(String testId) {
        return page.getByTestId(testId).isVisible();
    }

    // ==================== Screenshot Helpers ====================

    /**
     * Take a screenshot for debugging.
     */
    protected void takeScreenshot(String name) {
        page.screenshot(new Page.ScreenshotOptions()
                .setPath(Paths.get("./build", name + ".png")));
    }

    // ==================== Dialog Helpers ====================

    /**
     * Accept the next dialog (confirm, alert, etc.).
     */
    protected void acceptNextDialog() {
        page.onDialog(Dialog::accept);
    }

    /**
     * Dismiss the next dialog.
     */
    protected void dismissNextDialog() {
        page.onDialog(Dialog::dismiss);
    }
}
