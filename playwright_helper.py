#!/usr/bin/env python3
"""
Playwright Helper - Development Tool for Design/Debugging

This script uses Playwright to capture screenshots and analyze web pages visually.
It's intended for development use ONLY - not for production scraping.

Usage:
    # Take a screenshot of a page
    python playwright_helper.py screenshot https://example.com my_screenshot.png

    # Take a screenshot and wait for JavaScript
    python playwright_helper.py screenshot https://example.com my_screenshot.png --wait 5000

    # Capture full page screenshot
    python playwright_helper.py screenshot https://example.com my_screenshot.png --full-page

    # Interactive mode (launch browser and keep it open)
    python playwright_helper.py interactive https://example.com
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, Page


# Default configuration
DEFAULT_SCREENSHOT_DIR = Path("playwright-screenshots")
DEFAULT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def take_screenshot(url: str, output_path: str = None, wait_ms: int = 0, full_page: bool = False, headless: bool = True):
    """
    Take a screenshot of a webpage using Playwright.

    Args:
        url: The URL to screenshot
        output_path: Where to save the screenshot (defaults to playwright-screenshots/TIMESTAMP.png)
        wait_ms: Milliseconds to wait before taking screenshot (for JS loading)
        full_page: Capture the entire scrollable page
        headless: Run browser in headless mode (no UI)
    """
    # Use default directory and timestamp if no output specified
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = DEFAULT_SCREENSHOT_DIR / f"screenshot_{timestamp}.png"

    output = Path(output_path)

    # Create parent directory if it doesn't exist
    if output.parent != Path('.'):
        output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            print(f"[INFO] Navigating to {url}...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            if wait_ms > 0:
                print(f"[INFO] Waiting {wait_ms}ms for JavaScript to load...")
                page.wait_for_timeout(wait_ms)

            print(f"[INFO] Capturing screenshot...")
            page.screenshot(path=str(output), full_page=full_page)

            print(f"[SUCCESS] Screenshot saved to: {output.absolute()}")
            print(f"[INFO] Size: {output.stat().st_size / 1024:.1f} KB")

        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        browser.close()


def interactive_mode(url: str):
    """
    Launch a browser in non-headless mode for interactive debugging.

    Args:
        url: The URL to open
    """
    with sync_playwright() as p:
        print(f"[INFO] Launching browser for: {url}")
        print("[INFO] Browser will stay open until you close it...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        # Keep browser open until user closes it
        try:
            input("Press Enter to close browser...")
        except KeyboardInterrupt:
            pass

        browser.close()


def extract_text(url: str, selector: str = None):
    """
    Extract text from a webpage (useful for debugging scrapers).

    Args:
        url: The URL to scrape
        selector: Optional CSS selector to extract specific elements
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"[INFO] Loading {url}...")
            page.goto(url, wait_until="networkidle", timeout=30000)

            if selector:
                elements = page.query_selector_all(selector)
                print(f"\n[INFO] Found {len(elements)} elements matching '{selector}':\n")
                for i, el in enumerate(elements, 1):
                    text = el.inner_text()
                    print(f"{i}. {text[:100]}")
            else:
                text = page.inner_text("body")
                print(f"\n[INFO] Page text:\n")
                print(text[:1000])  # First 1000 chars

            browser.close()

        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Playwright Helper - Development tool for visual debugging"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Capture a screenshot")
    screenshot_parser.add_argument("url", help="URL to screenshot")
    screenshot_parser.add_argument("output", nargs='?', default=None,
                                   help="Output file path (default: playwright-screenshots/TIMESTAMP.png)")
    screenshot_parser.add_argument("--wait", type=int, default=0,
                                   help="Wait N milliseconds before screenshot (default: 0)")
    screenshot_parser.add_argument("--full-page", action="store_true",
                                   help="Capture full scrollable page")
    screenshot_parser.add_argument("--no-headless", action="store_true",
                                   help="Show browser window")

    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Launch interactive browser")
    interactive_parser.add_argument("url", help="URL to open")

    # Extract text command
    extract_parser = subparsers.add_parser("extract", help="Extract text from page")
    extract_parser.add_argument("url", help="URL to scrape")
    extract_parser.add_argument("--selector", help="CSS selector to extract")

    args = parser.parse_args()

    if args.command == "screenshot":
        take_screenshot(
            args.url,
            args.output,
            wait_ms=args.wait,
            full_page=args.full_page,
            headless=not args.no_headless
        )
    elif args.command == "interactive":
        interactive_mode(args.url)
    elif args.command == "extract":
        extract_text(args.url, args.selector)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
