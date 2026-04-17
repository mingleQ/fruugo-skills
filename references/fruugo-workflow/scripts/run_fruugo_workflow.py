#!/usr/bin/env python3
import argparse
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
WORKFLOW_ROOT = SCRIPT_DIR.parent
SKILL_ROOT = WORKFLOW_ROOT.parent.parent
DEFAULT_RUNTIME_DIR = SKILL_ROOT / "runtime"
DEFAULT_DB = DEFAULT_RUNTIME_DIR / "fruugo_product_links.sqlite3"
DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "templates" / "Prod_1772601378_NEW_FRU_GBR_01_1772601383ZJW031204.xlsx"
DEFAULT_CATEGORIES_CSV = SKILL_ROOT / "assets" / "categories" / "fruugo_categories_0325.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Fruugo workflow end to end: consume links, rewrite images through remote /api/store, then generate upload and inventory workbooks."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite tracker DB path.")
    parser.add_argument("--count", type=int, default=1, help="How many new tracker links to consume.")
    parser.add_argument("--output-dir", default="", help="Directory for generated CSV/XLSX files.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Fruugo upload template path.")
    parser.add_argument(
        "--categories-csv",
        default=str(DEFAULT_CATEGORIES_CSV),
        help="Category CSV used to bootstrap a fresh tracker when the DB is empty.",
    )
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
    parser.add_argument(
        "--bootstrap-pages",
        type=int,
        default=5,
        help="Pages per category when bootstrapping a fresh tracker.",
    )
    parser.add_argument(
        "--bootstrap-page-size",
        type=int,
        default=128,
        help="Products per page when bootstrapping a fresh tracker.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip category crawl bootstrap even if the tracker DB is empty.",
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
    output_dir = (
        Path(raw_output_dir)
        if raw_output_dir
        else DEFAULT_RUNTIME_DIR / "output" / date_code / f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def extract_path(label: str, text: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s+(.+)$", text, flags=re.M)
    if not match:
        raise ValueError(f"Could not find {label} path in output")
    return match.group(1).strip()


def tracker_has_urls(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'product_links'"
        ).fetchone()
        if not row or row[0] == 0:
            return False
        count = connection.execute("SELECT COUNT(*) FROM product_links").fetchone()[0]
        return count > 0


def bootstrap_tracker(args: argparse.Namespace, output_dir: Path) -> None:
    categories_csv = Path(args.categories_csv)
    if not categories_csv.exists():
        raise FileNotFoundError(f"Bootstrap category CSV not found: {categories_csv}")

    bootstrap_dir = output_dir / "bootstrap_category_links"
    crawl_cmd = [
        "node",
        str(SCRIPT_DIR / "crawl_fruugo_category_product_links.js"),
        "--input",
        str(categories_csv),
        "--output-dir",
        str(bootstrap_dir),
        "--pages",
        str(args.bootstrap_pages),
        "--page-size",
        str(args.bootstrap_page_size),
    ]
    import_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fruugo_link_tracker.py"),
        "import-csv",
        "--db",
        str(Path(args.db)),
        "--csv",
        str(bootstrap_dir / "all_category_product_links.csv"),
        "--url-column",
        "Product URL",
        "--source-label",
        "bootstrap-category-crawl",
    ]

    print("== Bootstrap tracker from bundled category CSV ==")
    run_step(crawl_cmd, SCRIPT_DIR)
    run_step(import_cmd, SCRIPT_DIR)


def main() -> int:
    args = parse_args()
    repo_root = SCRIPT_DIR
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_output_dir(args.output_dir, args.date_code)

    if not args.skip_bootstrap and not tracker_has_urls(db_path):
        bootstrap_tracker(args, output_dir)

    product_csv = output_dir / f"fruugo_products_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    consume_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "consume_fruugo_product_links.py"),
        "--db",
        str(db_path),
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
        str(SCRIPT_DIR / "rewrite_fruugo_product_csv_images.py"),
        "--input",
        str(product_csv),
        "--public-base",
        args.public_base,
        "--store-api",
        args.store_api,
    ]

    generate_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "generate_fruugo_xlsx.py"),
        "--template",
        str(Path(args.template)),
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
