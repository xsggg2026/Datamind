from __future__ import annotations

import argparse
from pathlib import Path

from src.datamind.downloader import download_from_manifest
from src.datamind.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automated public fund XBRL analysis pipeline",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=False,
        default=None,
        help="Input directory or single report file (.xbrl/.xml/.pdf)",
    )
    parser.add_argument(
        "--input-url",
        type=str,
        default=None,
        help="Single report URL (for example CSRC XBRL HTML page)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/fund_competitor_report.xlsx"),
        help="Path to generated Excel report",
    )
    parser.add_argument(
        "--brief",
        type=Path,
        default=Path("output/fund_competitor_report.md"),
        help="Path to generated markdown brief",
    )
    parser.add_argument(
        "--funds",
        type=str,
        default="",
        help="Comma-separated fund names to include",
    )
    parser.add_argument(
        "--download-manifest",
        type=Path,
        default=None,
        help="CSV manifest for batch downloading XBRL files (columns: url, filename optional)",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("data/downloaded_xbrl"),
        help="Directory to store downloaded XBRL files",
    )
    parser.add_argument(
        "--overwrite-download",
        action="store_true",
        help="Overwrite existing files when downloading",
    )
    parser.add_argument(
        "--full-html-tables",
        action="store_true",
        help="Keep all parsed HTML tables in Excel (default keeps selective core outputs only)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    fund_whitelist = [x.strip() for x in args.funds.split(",") if x.strip()]

    input_dir = args.input
    if args.download_manifest is not None:
        stats = download_from_manifest(
            manifest_path=args.download_manifest,
            output_dir=args.download_dir,
            overwrite=args.overwrite_download,
        )
        input_dir = args.download_dir
        print(
            "Download complete:",
            f"total={stats['total']}, downloaded={stats['downloaded']}, skipped={stats['skipped']}, failed={stats['failed']}",
        )

    if input_dir is None and args.input_url is None:
        input_dir = Path("data/sample_xbrl")

    cleaned = run_pipeline(
        input_dir=input_dir,
        output_excel=args.output,
        output_markdown=args.brief,
        fund_whitelist=fund_whitelist or None,
        input_url=args.input_url,
        include_raw_html_tables=args.full_html_tables,
    )

    print(f"Done. Parsed funds: {len(cleaned)}")
    print(f"Excel report: {args.output}")
    print(f"Brief report: {args.brief}")


if __name__ == "__main__":
    main()
