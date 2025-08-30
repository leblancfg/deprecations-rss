"""Anthropic deprecations scraper with individual model extraction."""

import asyncio
import dotenv
import os
from random import randint

from browser_use import Agent, Browser, BrowserProfile
from browser_use.llm import ChatAnthropic

dotenv.load_dotenv("~/.env")

TOKEN = os.getenv("ANTHROPIC_API_TOKEN")
assert TOKEN, "ANTHROPIC_API_TOKEN environment variable is required"
print(TOKEN)

SPEED_OPTIMIZATION_PROMPT = """
Speed optimization instructions:
- Be extremely concise and direct in your responses
- Get to the goal as quickly as possible
- Use multi-action sequences whenever possible to reduce steps
"""


class OpenAIScraper:
    """Scraper for OpenAI deprecations page. It's behind Cloudflare, etc. for
    some reason, so we have to use an agent."""

    provider_name = "OpenAI"
    url = "https://platform.openai.com/docs/deprecations"
    requires_playwright = False  # Agent handles it

    def extract_structured_deprecations(self):
        return []

    async def _extract_unstructured_deprecations(self):
        browser = Browser(
            headless=False,  # Show browser window
            window_size={
                "width": 1000 + randint(-100, 100),
                "height": 800 + randint(-100, 100),
            },
        )
        browser_profile = BrowserProfile(
            minimum_wait_page_load_time=0.1,
            wait_between_actions=0.1,
            headless=False,
        )
        llm = ChatAnthropic(
            base_url="https://api.anthropic.com",
            auth_token=TOKEN,
            model="claude-3-5-haiku-latest",
        )
        task = f"""
        Navigate to {self.url} and extract all deprecations, including model
        names, affected features, deprecation dates, and any relevant links.
        Format the output as a JSON array of objects with fields: model_name,
        feature, deprecation_date, link, and notes.
        """
        agent = Agent(
            task=task,
            llm=llm,
            flash_mode=True,
            browser_profile=browser_profile,
            browser=browser,
            extend_system_message=SPEED_OPTIMIZATION_PROMPT,
        )
        await agent.run()

    def extract_unstructured_deprecations(self):
        return asyncio.run(self._extract_unstructured_deprecations())
