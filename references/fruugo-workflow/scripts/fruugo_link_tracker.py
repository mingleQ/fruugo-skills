#!/usr/bin/env python3
import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_url(url: str) -> str:
    return (url or "").strip()


@dataclass
class LinkRecord:
    url: str
    status: str
    first_seen_at: str
    last_seen_at: str
    claimed_at: str
    completed_at: str
    failure_count: int
    last_error: str
    source_label: str


class LinkTracker:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS product_links (
                    url TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'new',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    claimed_at TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT '',
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    source_label TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_product_links_status_last_seen
                ON product_links(status, last_seen_at)
                """
            )

    def ensure_urls(self, urls: Iterable[str], source_label: str = "") -> int:
        now = utc_now()
        normalized = []
        seen = set()
        for raw in urls:
            url = normalize_url(raw)
            if not url or url in seen:
                continue
            seen.add(url)
            normalized.append((url, now, now, source_label))

        if not normalized:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO product_links (
                    url,
                    first_seen_at,
                    last_seen_at,
                    source_label
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    source_label = CASE
                        WHEN product_links.source_label = '' THEN excluded.source_label
                        ELSE product_links.source_label
                    END
                """,
                normalized,
            )
        return len(normalized)

    def claim_url(self, url: str, allow_failed: bool = True) -> bool:
        target = normalize_url(url)
        if not target:
            return False

        allowed_statuses = {"new"}
        if allow_failed:
            allowed_statuses.add("failed")

        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM product_links WHERE url = ?",
                (target,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO product_links (
                        url, status, first_seen_at, last_seen_at, claimed_at
                    ) VALUES (?, 'processing', ?, ?, ?)
                    """,
                    (target, now, now, now),
                )
                return True

            if row["status"] not in allowed_statuses:
                return False

            connection.execute(
                """
                UPDATE product_links
                SET status = 'processing',
                    claimed_at = ?,
                    last_seen_at = ?,
                    last_error = ''
                WHERE url = ?
                """,
                (now, now, target),
            )
        return True

    def mark_done(self, urls: Sequence[str]) -> int:
        normalized = [normalize_url(url) for url in urls if normalize_url(url)]
        if not normalized:
            return 0
        now = utc_now()
        with self._connect() as connection:
            connection.executemany(
                """
                UPDATE product_links
                SET status = 'done',
                    completed_at = ?,
                    last_seen_at = ?,
                    last_error = ''
                WHERE url = ?
                """,
                [(now, now, url) for url in normalized],
            )
        return len(normalized)

    def mark_failed(self, urls: Sequence[str], error_message: str) -> int:
        normalized = [normalize_url(url) for url in urls if normalize_url(url)]
        if not normalized:
            return 0
        now = utc_now()
        with self._connect() as connection:
            connection.executemany(
                """
                UPDATE product_links
                SET status = 'failed',
                    last_seen_at = ?,
                    last_error = ?,
                    failure_count = failure_count + 1
                WHERE url = ?
                """,
                [(now, error_message, url) for url in normalized],
            )
        return len(normalized)

    def claim_next_batch(self, limit: int, allow_failed: bool = True) -> List[str]:
        if limit <= 0:
            return []
        allowed_statuses = ["new"]
        if allow_failed:
            allowed_statuses.append("failed")

        now = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            placeholders = ", ".join("?" for _ in allowed_statuses)
            rows = connection.execute(
                f"""
                SELECT url
                FROM product_links
                WHERE status IN ({placeholders})
                ORDER BY first_seen_at, url
                LIMIT ?
                """,
                (*allowed_statuses, limit),
            ).fetchall()
            urls = [row["url"] for row in rows]
            connection.executemany(
                """
                UPDATE product_links
                SET status = 'processing',
                    claimed_at = ?,
                    last_seen_at = ?,
                    last_error = ''
                WHERE url = ?
                """,
                [(now, now, url) for url in urls],
            )
            connection.commit()
        return urls

    def reset_processing(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE product_links
                SET status = 'new',
                    claimed_at = '',
                    last_error = ''
                WHERE status = 'processing'
                """
            )
            return cursor.rowcount

    def stats(self) -> List[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM product_links
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()


def read_urls_from_csv(path: Path, url_column: str) -> List[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        field_map = {name.strip().lower(): name for name in reader.fieldnames}
        matched = field_map.get(url_column.strip().lower())
        if not matched:
            raise ValueError(f"URL column '{url_column}' not found in {path}")
        return [normalize_url(row.get(matched, "")) for row in reader if normalize_url(row.get(matched, ""))]


def read_urls_from_txt(path: Path) -> List[str]:
    return [normalize_url(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if normalize_url(line)]


def add_common_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", required=True, help="Path to the SQLite tracker database.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track Fruugo product-link consumption state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the tracker database if needed.")
    add_common_db_arg(init_parser)

    import_csv_parser = subparsers.add_parser("import-csv", help="Import product links from a CSV file.")
    add_common_db_arg(import_csv_parser)
    import_csv_parser.add_argument("--csv", required=True, help="CSV path that contains a URL column.")
    import_csv_parser.add_argument("--url-column", default="Product URL", help="Name of the URL column.")
    import_csv_parser.add_argument("--source-label", default="", help="Optional source label stored with the URLs.")

    import_txt_parser = subparsers.add_parser("import-txt", help="Import product links from a TXT file.")
    add_common_db_arg(import_txt_parser)
    import_txt_parser.add_argument("--txt", required=True, help="TXT path with one URL per line.")
    import_txt_parser.add_argument("--source-label", default="", help="Optional source label stored with the URLs.")

    stats_parser = subparsers.add_parser("stats", help="Show tracker status counts.")
    add_common_db_arg(stats_parser)

    claim_parser = subparsers.add_parser("claim", help="Claim the next batch of unconsumed links.")
    add_common_db_arg(claim_parser)
    claim_parser.add_argument("--limit", type=int, default=1, help="How many URLs to claim.")
    claim_parser.add_argument(
        "--skip-failed",
        action="store_true",
        help="Do not recycle failed URLs when claiming.",
    )

    mark_done_parser = subparsers.add_parser("mark-done", help="Mark URLs as done.")
    add_common_db_arg(mark_done_parser)
    mark_done_parser.add_argument("--txt", required=True, help="TXT file containing URLs to mark as done.")

    mark_failed_parser = subparsers.add_parser("mark-failed", help="Mark URLs as failed.")
    add_common_db_arg(mark_failed_parser)
    mark_failed_parser.add_argument("--txt", required=True, help="TXT file containing URLs to mark as failed.")
    mark_failed_parser.add_argument("--error", default="Unknown scrape error", help="Failure reason.")

    reset_parser = subparsers.add_parser("reset-processing", help="Reset processing URLs back to new.")
    add_common_db_arg(reset_parser)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tracker = LinkTracker(Path(args.db))

    if args.command == "init":
        print(f"Tracker ready: {args.db}")
        return 0

    if args.command == "import-csv":
        urls = read_urls_from_csv(Path(args.csv), args.url_column)
        imported = tracker.ensure_urls(urls, source_label=args.source_label or args.csv)
        print(f"Imported {imported} URLs from {args.csv}")
        return 0

    if args.command == "import-txt":
        urls = read_urls_from_txt(Path(args.txt))
        imported = tracker.ensure_urls(urls, source_label=args.source_label or args.txt)
        print(f"Imported {imported} URLs from {args.txt}")
        return 0

    if args.command == "stats":
        for row in tracker.stats():
            print(f"{row['status']},{row['count']}")
        return 0

    if args.command == "claim":
        claimed = tracker.claim_next_batch(args.limit, allow_failed=not args.skip_failed)
        for url in claimed:
            print(url)
        return 0

    if args.command == "mark-done":
        urls = read_urls_from_txt(Path(args.txt))
        count = tracker.mark_done(urls)
        print(f"Marked done: {count}")
        return 0

    if args.command == "mark-failed":
        urls = read_urls_from_txt(Path(args.txt))
        count = tracker.mark_failed(urls, args.error)
        print(f"Marked failed: {count}")
        return 0

    if args.command == "reset-processing":
        count = tracker.reset_processing()
        print(f"Reset processing: {count}")
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
