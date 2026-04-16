#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DB = Path("0326/fruugo_product_links.sqlite3")
DEFAULT_TEMPLATE = Path("0313/Prod_1772601378_NEW_FRU_GBR_01_1772601383ZJW031204.xlsx")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Fruugo workflow end to end: consume links, rewrite images through remote /api/store, then generate upload and inventory workbooks."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite tracker DB path.")
    parser.add_argument("--count", type=int, default=1, help="How many new tracker links to consume.")
    parser.add_argument("--output-dir", default="", help="Directory for generated CSV/XLSX files.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Fruugo upload template path.")
    parser.add_argument("--operator", default="SHOU", help="Operator prefix for vendor SKU.")
    parser.add_argument("--shop", default="07", help="Shop code for vendor SKU.")
    parser.add_argument(
        "--date-code",
        default=datetime.now().strftime("%m%d"),
        help="MMDD code for output naming and vendor SKU.",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Allow previously failed tracker URLs to be retried.",
    )
    parser.add_argument(
        "--reset-processing-first",
        action="store_true",
        help="Reset processing URLs back to new before claim.",
    )
    parser.add_argument(
        "--public-base",
        default="https://img.urlconverterecommerce.online",
        help="Public HTTPS base used for stored images.",
    )
    parser.add_argument(
        "--store-api",
        default="https://img.urlconverterecommerce.online/api/store",
        help="Remote urlconverter store API endpoint.",
    )
    return parser.parse_args()


def run_step(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result.stdout


def ensure_output_dir(raw_output_dir: str, date_code: str) -> Path:
    output_dir = Path(raw_output_dir) if raw_output_dir else Path(date_code) / f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def extract_path(label: str, text: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s+(.+)$", text, flags=re.M)
    if not match:
        raise ValueError(f"Could not find {label} path in output")
    return match.group(1).strip()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    output_dir = ensure_output_dir(args.output_dir, args.date_code)

    product_csv = output_dir / f"fruugo_products_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    consume_cmd = [
        sys.executable,
        "consume_fruugo_product_links.py",
        "--db",
        args.db,
        "--count",
        str(args.count),
        "--output",
        str(product_csv),
    ]
    if args.include_failed:
        consume_cmd.append("--include-failed")
    if args.reset_processing_first:
        consume_cmd.append("--reset-processing-first")

    rewrite_cmd = [
        sys.executable,
        "rewrite_fruugo_product_csv_images.py",
        "--input",
        str(product_csv),
        "--public-base",
        args.public_base,
        "--store-api",
        args.store_api,
    ]

    generate_cmd = [
        sys.executable,
        "generate_fruugo_xlsx.py",
        "--template",
        args.template,
        "--input",
        str(product_csv),
        "--operator",
        args.operator,
        "--shop",
        args.shop,
        "--date-code",
        args.date_code,
        "--inventory-dir",
        str(output_dir),
    ]

    print("== Consume product links ==")
    run_step(consume_cmd, repo_root)

    print("== Rewrite product CSV images via remote /api/store ==")
    run_step(rewrite_cmd, repo_root)

    print("== Generate Fruugo upload and inventory workbooks ==")
    generate_output = run_step(generate_cmd, repo_root)
    upload_workbook = extract_path("Generated", generate_output)
    inventory_workbook = extract_path("Inventory", generate_output)

    print("== Workflow outputs ==")
    print(f"Product CSV: {product_csv}")
    print(f"Upload workbook: {upload_workbook}")
    print(f"Inventory workbook: {inventory_workbook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
