import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://platform.openai.com/docs/deprecations")
    page.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2/av0/rcv/5d91x/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal/auto/\"]").content_frame.locator("body").click()
    page.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2/av0/rcv/ssaus/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal/auto/\"]").content_frame.locator("body").click()
    page.goto("chrome-error://chromewebdata/")
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
