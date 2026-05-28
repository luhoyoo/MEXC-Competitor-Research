from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
from PIL import Image

from .scraper import DEFAULT_HEADERS


@dataclass(frozen=True)
class DownloadedImage:
    path: Path
    width: int
    height: int
    sha256: str


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def download_image(
    image_url: str,
    output_dir: Path,
    prefix: str,
    min_width: int = 240,
    min_height: int = 120,
    timeout: int = 30,
) -> DownloadedImage | None:
    if not image_url:
        return None
    response = None
    final_url = image_url
    last_error = None
    for candidate_url in candidate_image_urls(image_url):
        try:
            response = requests.get(candidate_url, headers=DEFAULT_HEADERS, timeout=timeout)
            response.raise_for_status()
            final_url = candidate_url
            break
        except requests.RequestException as exc:
            last_error = exc
            response = None
            continue

    if response is None:
        print(f"[download] 下载失败 {image_url}: {last_error}")
        return None

    if final_url != image_url:
        print(f"[download] 原链接参数失效，已改用原图链接：{final_url}")

    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if content_type and not content_type.startswith("image/"):
        print(f"[download] 跳过非图片资源 {final_url}: {content_type}")
        return None

    content = response.content
    sha256 = hashlib.sha256(content).hexdigest()
    ext = pick_extension(final_url, content_type)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = (output_dir / f"{prefix}-{sha256[:12]}{ext}").resolve()
    if not path.exists():
        path.write_bytes(content)

    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception as exc:
        print(f"[download] 图片无法识别 {final_url}: {exc}")
        return None

    if width < min_width or height < min_height:
        print(f"[download] 跳过尺寸过小图片 {final_url}: {width}x{height}")
        return None

    return DownloadedImage(path=path, width=width, height=height, sha256=sha256)


def pick_extension(image_url: str, content_type: str) -> str:
    if content_type in CONTENT_TYPE_EXTENSIONS:
        return CONTENT_TYPE_EXTENSIONS[content_type]
    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    guessed = mimetypes.guess_extension(content_type) if content_type else None
    return guessed or ".jpg"


def candidate_image_urls(image_url: str) -> list[str]:
    parsed = urlparse(image_url)
    urls = [image_url]
    if parsed.query:
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        urls.append(clean)
    return list(dict.fromkeys(urls))
