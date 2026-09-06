from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .analysis import build_analysis_tables
from .cleaning import clean_dataframe
from .html_parser import extract_html_detail_tables, parse_html_url
from .pdf_tables import extract_pdf_detail_tables
from .record_tables import synthesize_selected_tables
from .reporting import write_excel_report, write_markdown_brief
from .xbrl_parser import parse_folder

SELECTED_SHEET_NAMES = {
    "表01_基本信息",
    "表02_主要财务指标",
    "表03_净值表现",
    "表04_资产负债表",
    "表05_利润表",
    "表06_净资产变动表",
    "表07_投资组合报告",
    "表08_前十大持仓",
    "表09_行业配置",
    "表10_基金持有人结构",
    "表11_新发与募集信息",
}


def run_pipeline(
    input_dir: Optional[Path],
    output_excel: Path,
    output_markdown: Optional[Path] = None,
    fund_whitelist: Optional[Iterable[str]] = None,
    input_url: Optional[str] = None,
    include_raw_html_tables: bool = False,
) -> pd.DataFrame:
    records = []
    if input_dir is not None:
        records.extend(parse_folder(input_dir))
    if input_url:
        records.extend(parse_html_url(input_url))

    if not records:
        source_hint = input_url or input_dir
        raise ValueError(f"No parseable XBRL/XML/PDF/HTML content found at: {source_hint}")

    df = pd.DataFrame([r.to_dict() for r in records])
    cleaned = clean_dataframe(df)

    if fund_whitelist:
        targets = {x.strip().lower() for x in fund_whitelist if x.strip()}
        cleaned = cleaned[cleaned["fund_name"].str.lower().isin(targets)].copy()

    tables = build_analysis_tables(cleaned)
    detail_tables = {}
    if input_dir is not None:
        detail_tables.update(extract_pdf_detail_tables(input_dir))
    if input_url:
        detail_tables.update(
            extract_html_detail_tables(
                input_url,
                include_raw_tables=include_raw_html_tables,
            )
        )

    selective_url_mode = bool(input_url) and not include_raw_html_tables
    write_excel_report(
        output_excel,
        cleaned,
        tables,
        extra_tables=detail_tables,
        include_analysis_sheets=not selective_url_mode,
    )

    if output_excel.exists():
        try:
            present = set(pd.read_excel(output_excel, sheet_name=None, nrows=0).keys())
        except Exception:
            present = set()
        missing_selected = SELECTED_SHEET_NAMES - present
        if missing_selected:
            synthesized = synthesize_selected_tables(cleaned)
            with pd.ExcelWriter(
                output_excel,
                engine="openpyxl",
                mode="a",
                if_sheet_exists="replace",
            ) as writer:
                for name in sorted(missing_selected):
                    synthesized[name].to_excel(writer, sheet_name=name, index=False)

    if output_markdown is not None:
        write_markdown_brief(output_markdown, tables)

    return cleaned
