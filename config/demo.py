from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


TARGET_URL = "https://quotes.toscrape.com/"
OUTPUT_FILE = Path(__file__).with_name("demo_output.txt")
MAX_ITEMS = 10
USE_PLAYWRIGHT_FALLBACK = True
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def fetch_html_requests(url: str) -> str:
    """Fetch HTML with requests for simple static pages."""
    response = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    return response.text


def parse_quotes_from_html(html: str) -> list[dict[str, str]]:
    """Parse quote text and author from the target page."""
    if BeautifulSoup is None:
        raise RuntimeError(
            "缺少 beautifulsoup4。"
            f"请在当前解释器安装: {sys.executable} -m pip install beautifulsoup4 lxml"
        )

    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, str]] = []

    for block in soup.select(".quote"):
        quote_node = block.select_one(".text")
        author_node = block.select_one(".author")

        if not quote_node or not author_node:
            continue

        quote = quote_node.get_text(strip=True)
        author = author_node.get_text(strip=True)
        if not quote or not author:
            continue

        items.append({"quote": quote, "author": author})
        if len(items) >= MAX_ITEMS:
            break

    return items


def fetch_html_playwright(url: str) -> str:
    """Fetch HTML with a real browser when static requests are not enough."""
    if sync_playwright is None:
        raise RuntimeError(
            "缺少 Playwright。"
            f"请在当前解释器安装: {sys.executable} -m pip install playwright "
            f"并执行: {sys.executable} -m playwright install chromium"
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            return page.content()
        finally:
            browser.close()


def save_to_txt(items: list[dict[str, str]], output_path: Path) -> None:
    """Write scraped items to a readable TXT file."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "Demo Spider Output",
        f"Source: {TARGET_URL}",
        f"Generated At: {generated_at}",
        f"Total Items: {len(items)}",
        "",
    ]

    for index, item in enumerate(items, start=1):
        lines.append(f'{index}. "{item["quote"]}"')
        lines.append(f'   作者: {item["author"]}')
        lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    print(f"开始抓取: {TARGET_URL}")

    items: list[dict[str, str]] = []
    method_used = ""
    request_error: Exception | None = None

    try:
        html = fetch_html_requests(TARGET_URL)
        items = parse_quotes_from_html(html)
        method_used = "requests"
    except requests.RequestException as exc:
        request_error = exc
        print(f"requests 抓取失败: {exc}")
    except Exception as exc:
        request_error = exc
        print(f"requests 抓取出现异常: {exc}")

    if not items and USE_PLAYWRIGHT_FALLBACK:
        print("静态抓取无结果，尝试使用 Playwright 兜底...")
        try:
            html = fetch_html_playwright(TARGET_URL)
            items = parse_quotes_from_html(html)
            method_used = "playwright fallback"
        except Exception as exc:
            print(f"Playwright 抓取失败: {exc}")
            if request_error is not None:
                print(f"初始 requests 错误: {request_error}")

    if not items:
        print("未解析到任何内容，程序结束。")
        return 1

    save_to_txt(items, OUTPUT_FILE)
    print(f"抓取方式: {method_used}")
    print(f"成功抓取 {len(items)} 条")
    print(f"结果已保存到: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
