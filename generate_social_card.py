#!/usr/bin/env python3
"""
Generate social card image from HTML template.
Requires playwright: pip install playwright && playwright install
"""

import asyncio
import os
from playwright.async_api import async_playwright


async def generate_social_card():
    """Generate social card image from HTML template."""

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_file = os.path.join(script_dir, "docs", "social-card.html")
    output_file = os.path.join(script_dir, "docs", "social-card.png")

    if not os.path.exists(html_file):
        print(f"Error: HTML file not found at {html_file}")
        return

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Set viewport to social card dimensions
        await page.set_viewport_size({"width": 1200, "height": 630})

        # Load the HTML file
        await page.goto(f"file://{html_file}")

        # Wait for fonts to load
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)  # Additional wait for font rendering

        # Take screenshot
        await page.screenshot(path=output_file, full_page=True)

        await browser.close()

        print(f"✅ Social card generated: {output_file}")


if __name__ == "__main__":
    asyncio.run(generate_social_card())
