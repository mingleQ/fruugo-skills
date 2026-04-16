#!/usr/bin/env python3
import argparse
import csv
from datetime import datetime
from pathlib import Path

from fruugo_link_tracker import LinkTracker
from generate_fruugo_xlsx import parse_product_page


FIELDNAMES = [
    "url",
    "title",
    "description",
    "rrp",
    "category",
    "color",
    "size",
    "barcode",
    "images",
    "consumed_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Claim Fruugo product links from the tracker, scrape details, and write a product table CSV."
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite tracker DB.")
    parser.add_argument("--count", type=int, default=50, help="How many new links to consume. Default: 50.")
    parser.add_argument(
        "--output",
        default="",
        help="Output product-table CSV path. Defaults to ./0330/fruugo_products_consumed_<timestamp>.csv",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Allow previously failed URLs to be claimed again.",
    )
    parser.add_argument(
        "--reset-processing-first",
        action="store_true",
        help="Reset lingering processing URLs back to new before claiming.",
    )
    return parser.parse_args()


def build_default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("0330") / f"fruugo_products_consumed_{timestamp}.csv"


def ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()


def append_row(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writerow(row)
        handle.flush()


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise ValueError("--count must be greater than 0")

    output_path = Path(args.output) if args.output else build_default_output_path()
    ensure_csv_header(output_path)

    tracker = LinkTracker(Path(args.db))
    if args.reset_processing_first:
        reset_count = tracker.reset_processing()
        print(f"Reset processing URLs: {reset_count}")

    claimed_urls = tracker.claim_next_batch(args.count, allow_failed=args.include_failed)
    if not claimed_urls:
        print("No eligible URLs available to consume.")
        return 0

    print(f"Claimed {len(claimed_urls)} URLs")

    success_count = 0
    failed_count = 0
    for index, url in enumerate(claimed_urls, start=1):
        try:
            print(f"[{index}/{len(claimed_urls)}] Scraping {url}")
            scraped = parse_product_page(url)
            row = {
                "url": url,
                "title": scraped.get("title", ""),
                "description": scraped.get("description", ""),
                "rrp": scraped.get("rrp", ""),
                "category": scraped.get("category", ""),
                "color": scraped.get("color", ""),
                "size": scraped.get("size", ""),
                "barcode": scraped.get("barcode", ""),
                "images": scraped.get("images", ""),
                "consumed_at": datetime.now().isoformat(timespec="seconds"),
            }
            append_row(output_path, row)
            tracker.mark_done([url])
            success_count += 1
        except Exception as exc:
            tracker.mark_failed([url], str(exc))
            failed_count += 1
            print(f"FAILED {url}: {exc}")

    print(f"Output: {output_path}")
    print(f"Succeeded: {success_count}")
    print(f"Failed: {failed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
