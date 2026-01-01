package de.segelbundesliga.e2e;

import static de.segelbundesliga.e2e.TestFixtures.*;

import com.microsoft.playwright.*;

/**
 * Thread-safe Playwright instance management.
 * Allows reusing browser state across tests.
 */
public class PlaywrightThreadFactory {

    public static final ThreadLocal<Playwright> playwrightThread = new ThreadLocal<>();
    public static final ThreadLocal<Browser> browserThread = new ThreadLocal<>();
    public static final ThreadLocal<BrowserContext> browserContextThread = new ThreadLocal<>();
    public static final ThreadLocal<Page> pageThread = new ThreadLocal<>();

    /**
     * Get or create a Page instance.
     *
     * @param reuseExistingLoginState If true, load storage state from file (for authenticated tests)
     * @return A Playwright Page instance
     */
    public static Page getPage(boolean reuseExistingLoginState) {
        if (playwrightThread.get() == null) {
            Playwright playwright = Playwright.create();
            playwrightThread.set(playwright);
            Page page = createPage(playwright, reuseExistingLoginState);
            pageThread.set(page);
        }
        return pageThread.get();
    }

    private static Page createPage(Playwright playwright, boolean reuseExistingLoginState) {
        Browser browser = launchBrowser(
                playwright,
                new BrowserType.LaunchOptions()
                        .setHeadless(config.getHeadless())
                        .setSlowMo(DELAY_IN_MS));

        BrowserContext context;
        Browser.NewContextOptions contextOptions = new Browser.NewContextOptions()
                .setLocale("de-DE")
                .setTimezoneId("Europe/Berlin")
                .setViewportSize(getViewportSize())
                .setIgnoreHTTPSErrors(true);

        if (reuseExistingLoginState && CONTEXT_STATE_PATH.toFile().exists()) {
            context = browser.newContext(contextOptions.setStorageStatePath(CONTEXT_STATE_PATH));
        } else {
            context = browser.newContext(contextOptions);
        }

        browserThread.set(browser);
        browserContextThread.set(context);
        return context.newPage();
    }

    /**
     * Close the current page and playwright instance.
     */
    public static void closePage() {
        Playwright playwright = playwrightThread.get();
        Page page = pageThread.get();
        Browser browser = browserThread.get();
        BrowserContext context = browserContextThread.get();

        if (page != null) {
            page.close();
            pageThread.remove();
        }
        if (context != null) {
            context.close();
            browserContextThread.remove();
        }
        if (browser != null) {
            browser.close();
            browserThread.remove();
        }
        if (playwright != null) {
            playwright.close();
            playwrightThread.remove();
        }
    }

    /**
     * Save the current browser storage state (cookies, localStorage, etc.)
     * for reuse in subsequent tests.
     */
    public static void saveStorageState() {
        BrowserContext context = browserContextThread.get();
        if (context != null) {
            context.storageState(new BrowserContext.StorageStateOptions()
                    .setPath(CONTEXT_STATE_PATH));
        }
    }
}
