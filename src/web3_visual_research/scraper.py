from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .config import Competitor


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


@dataclass
class ScrapedVisual:
    run_date: str
    competitor_name: str
    competitor_slug: str
    source_type: str
    source_url: str
    page_url: str
    page_title: str | None
    published_at: str | None
    image_url: str
    visual_type: str

    def to_record(self) -> dict[str, str | None]:
        return asdict(self)


def scrape_competitor(
    competitor: Competitor,
    run_date: str,
    use_playwright: bool = False,
    limit_per_source: int = 12,
) -> list[ScrapedVisual]:
    visuals: list[ScrapedVisual] = []
    sources: list[tuple[str, str | None, str]] = [
        ("homepage", competitor.homepage, "官网首页 Banner / 页面视觉"),
        ("blog", competitor.blog, "Blog / Academy 封面图"),
    ]

    for source_type, url, visual_type in sources:
        if not url:
            continue
        html = fetch_html(url, use_playwright=use_playwright)
        if not html:
            continue
        page = parse_page(html, url)
        for image_url in page["image_urls"][:limit_per_source]:
            visuals.append(
                ScrapedVisual(
                    run_date=run_date,
                    competitor_name=competitor.name,
                    competitor_slug=competitor.slug,
                    source_type=source_type,
                    source_url=url,
                    page_url=url,
                    page_title=page["title"],
                    published_at=page["published_at"],
                    image_url=image_url,
                    visual_type=visual_type,
                )
            )
    return visuals


def scrape_social_competitor(
    competitor: Competitor,
    run_date: str,
    limit_per_source: int = 12,
    timezone_name: str = "Asia/Shanghai",
) -> list[ScrapedVisual]:
    visuals: list[ScrapedVisual] = []
    if competitor.x:
        visuals.extend(
            scrape_x_images(
                competitor=competitor,
                run_date=run_date,
                profile_url=competitor.x,
                limit=limit_per_source,
                timezone_name=timezone_name,
            )
        )
    if competitor.instagram:
        visuals.extend(
            scrape_instagram_images(
                competitor=competitor,
                run_date=run_date,
                profile_url=competitor.instagram,
                limit=limit_per_source,
                timezone_name=timezone_name,
            )
        )
    return visuals


def scrape_x_images(
    competitor: Competitor,
    run_date: str,
    profile_url: str,
    limit: int,
    timezone_name: str,
) -> list[ScrapedVisual]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[social] Playwright 未安装，无法抓取 X/Twitter。")
        return []

    visuals: list[ScrapedVisual] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1440, "height": 1200},
            )
            page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            seen: set[tuple[str, str]] = set()
            for _ in range(5):
                posts = page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('article')).map((article) => {
                      const time = article.querySelector('time');
                      const status = Array.from(article.querySelectorAll('a[href*="/status/"]'))
                        .map((a) => a.href)[0] || location.href;
                      const text = (article.innerText || '').trim();
                      const images = Array.from(article.querySelectorAll('img'))
                        .map((img) => img.src)
                        .filter((src) => src.includes('pbs.twimg.com/media'));
                      return {
                        url: status,
                        text,
                        publishedAt: time ? time.getAttribute('datetime') : null,
                        images
                      };
                    })
                    """
                )
                for post in posts:
                    if not is_same_local_date(post.get("publishedAt"), run_date, timezone_name):
                        continue
                    title = compact_title(post.get("text")) or f"{competitor.name} X/Twitter 当日动态"
                    for image_url in post.get("images", []):
                        key = (post.get("url") or profile_url, image_url)
                        if key in seen:
                            continue
                        seen.add(key)
                        visuals.append(
                            ScrapedVisual(
                                run_date=run_date,
                                competitor_name=competitor.name,
                                competitor_slug=competitor.slug,
                                source_type="x",
                                source_url=profile_url,
                                page_url=post.get("url") or profile_url,
                                page_title=title,
                                published_at=post.get("publishedAt"),
                                image_url=image_url,
                                visual_type="X/Twitter 宣传图",
                            )
                        )
                        if len(visuals) >= limit:
                            browser.close()
                            return visuals
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(2500)
            browser.close()
    except Exception as exc:
        print(f"[social] X/Twitter 抓取失败 {profile_url}: {exc}")
    return visuals


def scrape_instagram_images(
    competitor: Competitor,
    run_date: str,
    profile_url: str,
    limit: int,
    timezone_name: str,
) -> list[ScrapedVisual]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[social] Playwright 未安装，无法抓取 Instagram。")
        return []

    visuals: list[ScrapedVisual] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1440, "height": 1200},
            )
            page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            post_urls = collect_instagram_post_urls(page, profile_url, limit * 3)
            seen_images: set[str] = set()
            for post_url in post_urls:
                page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                post = page.evaluate(
                    """
                    () => {
                      const time = document.querySelector('time');
                      const ogTitle = document.querySelector('meta[property="og:title"]');
                      const ogImage = document.querySelector('meta[property="og:image"]');
                      const desc = document.querySelector('meta[property="og:description"]');
                      const images = Array.from(document.querySelectorAll('article img'))
                        .map((img) => img.src)
                        .filter(Boolean);
                      if (ogImage && ogImage.content) images.unshift(ogImage.content);
                      return {
                        url: location.href,
                        text: (desc && desc.content) || (ogTitle && ogTitle.content) || document.title,
                        publishedAt: time ? time.getAttribute('datetime') : null,
                        images
                      };
                    }
                    """
                )
                if not is_same_local_date(post.get("publishedAt"), run_date, timezone_name):
                    continue
                title = compact_title(post.get("text")) or f"{competitor.name} Instagram 当日动态"
                for image_url in post.get("images", []):
                    if "cdninstagram" not in image_url or image_url in seen_images:
                        continue
                    seen_images.add(image_url)
                    visuals.append(
                        ScrapedVisual(
                            run_date=run_date,
                            competitor_name=competitor.name,
                            competitor_slug=competitor.slug,
                            source_type="instagram",
                            source_url=profile_url,
                            page_url=post.get("url") or post_url,
                            page_title=title,
                            published_at=post.get("publishedAt"),
                            image_url=image_url,
                            visual_type="Instagram 宣传图",
                        )
                    )
                    if len(visuals) >= limit:
                        browser.close()
                        return visuals
            browser.close()
    except Exception as exc:
        print(f"[social] Instagram 抓取失败 {profile_url}: {exc}")
    return visuals


def collect_instagram_post_urls(page, profile_url: str, limit: int) -> list[str]:
    urls: list[str] = []
    for _ in range(4):
        found = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'))
              .map((a) => a.href)
            """
        )
        for url in found:
            if url.startswith("http") and url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(2000)
    return urls


def fetch_html(url: str, use_playwright: bool = False, timeout: int = 25) -> str | None:
    if use_playwright:
        rendered = fetch_html_with_playwright(url)
        if rendered:
            return rendered

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        print(f"[scraper] 请求失败 {url}: {exc}")
        return None


def fetch_html_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[scraper] Playwright 未安装，改用 requests。")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=45000)
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        print(f"[scraper] Playwright 渲染失败 {url}: {exc}")
        return None


def parse_page(html: str, base_url: str) -> dict[str, str | list[str] | None]:
    soup = BeautifulSoup(html, "html.parser")
    title = first_non_empty(
        meta_content(soup, "property", "og:title"),
        meta_content(soup, "name", "twitter:title"),
        soup.title.string.strip() if soup.title and soup.title.string else None,
    )
    published_at = first_non_empty(
        meta_content(soup, "property", "article:published_time"),
        meta_content(soup, "name", "date"),
        first_time_datetime(soup),
    )
    image_urls = list(dict.fromkeys(extract_image_urls(soup, base_url)))
    return {"title": title, "published_at": published_at, "image_urls": image_urls}


def extract_image_urls(soup: BeautifulSoup, base_url: str) -> Iterable[str]:
    for attr_name, attr_value in [
        ("property", "og:image"),
        ("property", "og:image:secure_url"),
        ("name", "twitter:image"),
        ("name", "twitter:image:src"),
    ]:
        url = meta_content(soup, attr_name, attr_value)
        if url:
            yield normalize_url(url, base_url)

    for source in soup.select("source[srcset], img[srcset]"):
        first = first_srcset_url(source.get("srcset"))
        if first:
            yield normalize_url(first, base_url)

    for img in soup.find_all("img"):
        raw_url = first_non_empty(
            img.get("src"),
            img.get("data-src"),
            img.get("data-original"),
            img.get("data-lazy-src"),
        )
        if raw_url:
            yield normalize_url(raw_url, base_url)


def normalize_url(raw_url: str, base_url: str) -> str:
    url = raw_url.strip()
    if not url or url.startswith("data:"):
        return ""
    if url.startswith("//"):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}:{url}"
    return urljoin(base_url, url)


def meta_content(soup: BeautifulSoup, attr_name: str, attr_value: str) -> str | None:
    tag = soup.find("meta", attrs={attr_name: attr_value})
    content = tag.get("content") if tag else None
    return content.strip() if content else None


def first_time_datetime(soup: BeautifulSoup) -> str | None:
    tag = soup.find("time")
    value = tag.get("datetime") if tag else None
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value.strip()


def first_srcset_url(srcset: str | None) -> str | None:
    if not srcset:
        return None
    first = srcset.split(",")[0].strip()
    return first.split(" ")[0].strip() if first else None


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def is_same_local_date(value: str | None, run_date: str, timezone_name: str) -> bool:
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
        return dt.astimezone(ZoneInfo(timezone_name)).date().isoformat() == run_date
    except ValueError:
        return value[:10] == run_date


def compact_title(text: str | None, max_length: int = 120) -> str | None:
    if not text:
        return None
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1] + "…"
