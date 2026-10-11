# Playwright in the sandbox shows every cross-origin image as broken, even with the proxy's credentials; route them through route.fetch

**Symptom** — A page that hotlinks pictures from another host (Wikimedia, deutsche-segelbundesliga.de) renders them as broken images in a Playwright screenshot: `img.complete && naturalWidth === 0`, the alt text in the box. `curl` fetches the same URL with 200, and `page.goto(<the image URL>)` in the same browser shows it fine.

**Cause** — The sandbox's egress proxy wants authentication. Chromium sends the credentials passed to `chromium.launch({ proxy: { username, password } })` when a *navigation* gets a 407, but not for a *subresource* (an `<img>` inside a page): that CONNECT comes back `407 Proxy Authentication Required`, then `net::ERR_TUNNEL_CONNECTION_FAILED`. Nothing is wrong with the page, the host, or a CSP. What misled me: the same symptom had been real once — hotlinked Wikimedia images also failed in the user's own browser — so "hotlinking is blocked" looked like the cause twice, while the second time it was only the test harness.

**Rule** — Before you blame a host for refusing hotlinks, log `requestfailed` and the response status of the image request *inside the page*. A 407 means the sandbox, not the site. To see the page as a user would, route the host through Playwright's own request stack, which does authenticate:

```js
await context.route("https://deutsche-segelbundesliga.de/**",
  async (route) => route.fulfill({ response: await route.fetch() }));
```

and declare the host in the Bash call's `allowed_domains`. Whether a real browser can hotlink the host is a separate question that only a real browser (or the user) answers.

**Evidence** — On `/prototype/dsbl/standings`: without the route, `407 DSC07807-1536x1024.jpg` and `FAIL … net::ERR_TUNNEL_CONNECTION_FAILED`; with the route, 0 broken images on all seven checked pages. `curl -sI` of the same image shows no `Cross-Origin-Resource-Policy`, CSP or referer check.

**Seen** — 2026-10-11, building the option-E prototype (issue #14); earlier the same day with the Wikimedia photos of the wireframes (issue #13).
