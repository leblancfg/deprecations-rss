#!/usr/bin/env python3
"""Run the complete scraping and RSS generation pipeline."""

import subprocess
import sys


def run_command(cmd):
    """Run a command and exit on failure."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"Failed: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    # Scrape all providers
    run_command("python -m src.main")

    # Generate RSS feed
    run_command("python -m src.rss_gen")

    print("\n✅ Pipeline complete!")
