#!/usr/bin/env python3
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError


DEFAULT_PUBLIC_BASE = "https://img.urlconverterecommerce.online"
DEFAULT_URLCONVERTER_DIR = Path("/Users/miles/Desktop/ecommerce/urlconverter")
DEFAULT_STORE_API = DEFAULT_PUBLIC_BASE + "/api/store"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite Fruugo product CSV image URLs to self-hosted HTTPS URLs."
    )
    parser.add_argument("--input", required=True, help="Path to the product CSV to rewrite.")
    parser.add_argument(
        "--public-base",
        default=DEFAULT_PUBLIC_BASE,
        help="Public HTTPS base for stored images.",
    )
    parser.add_argument(
        "--urlconverter-dir",
        default=str(DEFAULT_URLCONVERTER_DIR),
        help="Path to the local urlconverter directory.",
    )
    parser.add_argument(
        "--storage-dir",
        default="",
        help="Optional override for the local stored image directory.",
    )
    parser.add_argument(
        "--backup",
        default="",
        help="Optional backup CSV path. Defaults to <input>.orig.csv if missing.",
    )
    parser.add_argument(
        "--store-api",
        default=DEFAULT_STORE_API,
        help="Remote urlconverter store API. Set empty to disable remote storage.",
    )
    return parser.parse_args()


def ensure_backup(input_path: Path, backup_path: Path) -> None:
    if backup_path.exists():
        return
    shutil.copy2(input_path, backup_path)


def store_image_via_api(image_url: str, store_api: str) -> str:
    payload = json.dumps({"url": image_url}).encode("utf-8")
    request = Request(
        store_api,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = build_opener()
    with opener.open(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))
    output = str(result.get("output", "")).strip()
    if not result.get("ok") or not output:
        raise RuntimeError(result.get("error") or "remote store api failed")
    return output


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    urlconverter_dir = Path(args.urlconverter_dir)
    use_local_fallback = urlconverter_dir.exists()
    storage_dir = Path(args.storage_dir) if args.storage_dir else urlconverter_dir / "stored"
    if use_local_fallback:
        storage_dir.mkdir(parents=True, exist_ok=True)

    backup_path = Path(args.backup) if args.backup else input_path.with_suffix(".orig.csv")
    ensure_backup(input_path, backup_path)

    if use_local_fallback:
        sys.path.insert(0, str(urlconverter_dir))
        from storelib import build_public_url, store_image  # noqa: E402
    else:
        build_public_url = None
        store_image = None

    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "images" not in fieldnames:
            raise ValueError("CSV is missing the images column")
        rows = list(reader)

    updated_rows = []
    updated_images = 0
    fallback_images = 0
    remote_api_success = 0
    remote_api_failed = 0

    for row in rows:
        raw_images = [item.strip() for item in str(row.get("images", "")).split("|") if item.strip()]
        converted_images = []
        for image_url in raw_images:
            try:
                if args.store_api.strip():
                    converted_images.append(store_image_via_api(image_url, args.store_api.strip()))
                    updated_images += 1
                    remote_api_success += 1
                    continue
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError):
                remote_api_failed += 1

            if use_local_fallback:
                try:
                    relpath = store_image(image_url, storage_dir)
                    converted_images.append(build_public_url(args.public_base, relpath))
                    updated_images += 1
                    continue
                except Exception:
                    pass

            converted_images.append(None)

        fallback_source = next((item for item in converted_images if item), None)
        final_images = []
        for original, converted in zip(raw_images, converted_images):
            if converted:
                final_images.append(converted)
            elif fallback_source:
                final_images.append(fallback_source)
                fallback_images += 1
            else:
                final_images.append(original)

        row["images"] = "|".join(final_images)
        updated_rows.append(row)

    with input_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    remaining_non_https = 0
    expected_prefix = args.public_base.rstrip("/") + "/stored/"
    for row in updated_rows:
        for image_url in [item.strip() for item in str(row.get("images", "")).split("|") if item.strip()]:
            if not image_url.startswith(expected_prefix):
                remaining_non_https += 1

    print(f"Input: {input_path}")
    print(f"Backup: {backup_path}")
    print(f"Rows: {len(updated_rows)}")
    print(f"Updated image URLs: {updated_images}")
    print(f"Remote API successes: {remote_api_success}")
    print(f"Remote API failures: {remote_api_failed}")
    print(f"Fallback image URLs: {fallback_images}")
    print(f"Remaining non-self-hosted URLs: {remaining_non_https}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
