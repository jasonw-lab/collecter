#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import shutil
from PIL import Image


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def http_get(url: str, timeout: int = 20, headers: dict | None = None) -> bytes:
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_vqd(query: str) -> str:
    url = f"https://duckduckgo.com/?q={quote_plus(query)}&iax=images&ia=images"
    body = http_get(url).decode("utf-8", errors="ignore")
    match = re.search(r'vqd="([^"]+)"', body)
    if not match:
        match = re.search(r"vqd='([^']+)'", body)
    if not match:
        raise RuntimeError("Failed to find vqd token from DuckDuckGo")
    return match.group(1)


def search_image_candidates(query: str) -> list[str]:
    vqd = fetch_vqd(query)
    url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={quote_plus(query)}&vqd={vqd}"
    payload = http_get(
        url,
        headers={
            "Referer": "https://duckduckgo.com/",
            "Accept": "application/json,text/javascript,*/*;q=0.1",
        },
    ).decode("utf-8", errors="ignore")
    data = json.loads(payload)
    results = data.get("results") or []
    candidates: list[str] = []
    for item in results:
        image_url = item.get("image")
        thumb_url = item.get("thumbnail")
        if image_url:
            candidates.append(image_url)
        if thumb_url:
            candidates.append(thumb_url)
    return candidates


def download_image(url: str, dest: Path, referer: str | None = None, timeout: int = 30) -> None:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def validate_and_convert_image(image_path: Path) -> bool:
    """
    画像ファイルを検証し、必要に応じて正しい形式に変換する

    Returns:
        True if image is valid or successfully converted, False otherwise
    """
    try:
        with Image.open(image_path) as img:
            # 画像が正常に開けるか確認
            img.verify()

        # 再度開いて形式をチェック（verify後は再度開く必要がある）
        with Image.open(image_path) as img:
            actual_format = img.format
            expected_format = image_path.suffix.upper().replace(".", "")

            # JPEGとJPGは同じとして扱う
            if expected_format == "JPG":
                expected_format = "JPEG"

            if actual_format != expected_format:
                print(f"Warning: {image_path.name} is {actual_format} format, converting to {expected_format}...", file=sys.stderr)
                # 正しい形式に変換
                if expected_format == "JPEG":
                    # JPEGの場合、RGBに変換（透明度を削除）
                    rgb_img = img.convert("RGB")
                    rgb_img.save(image_path, "JPEG", quality=95)
                else:
                    img.save(image_path, expected_format)
                print(f"Converted: {image_path.name} to {expected_format}", file=sys.stderr)

        return True
    except Exception as exc:
        print(f"Invalid image file: {image_path} ({exc})", file=sys.stderr)
        return False


def iter_products(csv_path: Path):
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download product images from the web based on the CSV file."
    )
    parser.add_argument("--csv", default="sample-products.csv", help="CSV file path")
    parser.add_argument("--images-dir", default="images", help="Destination directory")
    parser.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between requests")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--image-file", help="Download only this specific image file (e.g., 1015.jpg)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    images_dir = Path(args.images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for row in iter_products(csv_path):
        title = row.get("title", "").strip()
        image_name = row.get("imageFile", "").strip()
        if not title or not image_name:
            print(f"Skipping row with missing title/imageFile: {row}", file=sys.stderr)
            continue

        # 特定の画像ファイルのみを処理
        if args.image_file and image_name != args.image_file:
            continue

        dest_path = images_dir / image_name
        if dest_path.exists() and not args.overwrite:
            print(f"Skip existing: {dest_path}")
            continue

        query = title
        try:
            candidates = search_image_candidates(query)
            if not candidates:
                print(f"No image found for: {title}", file=sys.stderr)
                continue
            downloaded = False
            for candidate_url in candidates[:10]:
                try:
                    download_image(candidate_url, dest_path, referer="https://duckduckgo.com/")
                    # 画像の検証と変換
                    if validate_and_convert_image(dest_path):
                        print(f"Downloaded: {title} -> {dest_path}")
                        downloaded = True
                        break
                    else:
                        # 無効な画像の場合は削除して次を試す
                        dest_path.unlink(missing_ok=True)
                        print(f"Invalid image, trying next candidate for: {title}", file=sys.stderr)
                except (HTTPError, URLError) as exc:
                    print(f"Retry next image for: {title} ({exc})", file=sys.stderr)
            if not downloaded:
                print(f"Failed: {title} (all candidates blocked)", file=sys.stderr)
        except (json.JSONDecodeError, RuntimeError) as exc:
            print(f"Failed: {title} ({exc})", file=sys.stderr)
        time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
