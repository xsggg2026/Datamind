from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from pypdf import PdfReader


def _normalize(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def _read_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    return _normalize("\n".join((page.extract_text() or "") for page in reader.pages))


def _collect_pdf_files(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.pdf"))
    return []


def _find_line_values(text: str, label: str) -> List[str]:
    lines = text.split("\n")
    norm_label = re.sub(r"\s+", "", label)
    number_pattern = r"-?[0-9][0-9,]*(?:\.[0-9]+)?%?"

    for idx, line in enumerate(lines):
        if norm_label in re.sub(r"\s+", "", line):
            merged = line
            for jump in range(1, 4):
                if idx + jump < len(lines):
                    merged += " " + lines[idx + jump]
            values = re.findall(number_pattern, merged)
            if values:
                return values
    return []


def _find_line_values_in_section(text: str, label: str, section_start: str, section_end: str) -> List[str]:
    start_idx = text.rfind(section_start)
    if start_idx < 0:
        return _find_line_values(text, label)
    end_idx = text.find(section_end, start_idx + len(section_start))
    if end_idx < 0:
        end_idx = len(text)
    return _find_line_values(text[start_idx:end_idx], label)


def _pick_pair(text: str, label: str) -> Tuple[str, str]:
    values = _find_line_values(text, label)
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return values[0], ""
    return "", ""


def _pick_pair_in_section(text: str, label: str, section_start: str, section_end: str) -> Tuple[str, str]:
    values = _find_line_values_in_section(text, label, section_start, section_end)
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return values[0], ""
    return "", ""


_CLASS_HEADER_RE = re.compile(r"([AC])类?$")


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _extract_report_fund_name(text: str) -> str:
    for pattern in [r"基金名称\s+([^\n]+)", r"基金简称\s+([^\n]+)"]:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _fund_title_prefix(text: str) -> str:
    name = _compact_text(_extract_report_fund_name(text))
    if not name:
        return ""
    return re.sub(r"[AC]类?$", "", name)


def _is_fund_title_row(item: object, fund_prefix: str) -> bool:
    if not fund_prefix:
        return False
    return _compact_text(item).startswith(fund_prefix)


def _detect_class_header(compact: str, name_compact: str = "") -> Tuple[str, bool]:
    """Detect a share-class block header line such as '<中文基金名>A' / '<中文基金名>C类'."""
    if not compact or "%" in compact:
        return "", False
    if name_compact:
        if name_compact + "A" in compact:
            return "A", True
        if name_compact + "C" in compact:
            return "C", True
    match = _CLASS_HEADER_RE.search(compact)
    if match and len(compact) <= 60:
        return match.group(1), False
    return "", False


def _stage_header_follows(compacted_lines: List[str], header_index: int, max_lines: int = 6) -> bool:
    seen = 0
    for idx in range(header_index + 1, min(header_index + 12, len(compacted_lines))):
        text = compacted_lines[idx]
        if not text:
            continue
        if "阶段" in text:
            return True
        seen += 1
        if seen >= max_lines:
            break
    return False


def extract_class_growth_benchmark(
    full_text: str,
    fund_name: str = "",
) -> Dict[str, Tuple[str, str]]:
    """Parse per-share-class 1Y growth/benchmark from 3.2.1-style tables.

    Class blocks are located by the Chinese fund name taken from the report
    itself (基金名称), so any fund template works. When the given name does
    not match, a generic '<名称>A/C' header scan validated by a following
    阶段 table header is used as fallback.
    """
    result: Dict[str, Tuple[str, str]] = {}
    number_pattern = r"-?[0-9][0-9,]*(?:\.[0-9]+)?%"
    compacted = [_compact_text(line) for line in full_text.split("\n")]

    name_compact = _compact_text(fund_name) or _fund_title_prefix(full_text)
    if name_compact:
        name_compact = re.sub(r"[AC]类?$", "", name_compact)

    current_class = ""
    for idx, compact in enumerate(compacted):
        if not compact:
            continue
        letter, trusted = _detect_class_header(compact, name_compact)
        if letter and (trusted or _stage_header_follows(compacted, idx)):
            current_class = letter
            continue
        if current_class and "过去一年" in compact:
            values = re.findall(number_pattern, compact)
            if len(values) >= 3 and current_class not in result:
                # Row layout: 净值增长率, 增长率标准差, 基准收益率, 基准收益率标准差
                result[current_class] = (values[0], values[2])
    return result


def _slice_section(text: str, start: str, ends: Iterable[str]) -> str:
    start_idx = text.find(start)
    if start_idx < 0:
        return ""
    # Avoid selecting table-of-contents snippets; prefer body sections after "§8" when possible.
    body_anchor = text.rfind("§8 投资组合报告")
    if body_anchor >= 0 and start_idx < body_anchor:
        start_idx = text.find(start, body_anchor)
    if start_idx < 0:
        return ""
    end_idx = len(text)
    for end in ends:
        idx = text.find(end, start_idx + len(start))
        if idx >= 0:
            end_idx = min(end_idx, idx)
    return text[start_idx:end_idx]


def _slice_section_last(text: str, start: str, end: str) -> str:
    start_idx = text.rfind(start)
    if start_idx < 0:
        return ""
    end_idx = text.find(end, start_idx + len(start))
    if end_idx < 0:
        end_idx = len(text)
    return text[start_idx:end_idx]


def _pick_pair_regex(section: str, label_pattern: str) -> Tuple[str, str]:
    value = r"([\-]?[0-9][0-9,]*(?:\.[0-9]+)?%?)"
    pattern = re.compile(label_pattern + r"\s*" + value + r"\s+" + value)
    match = pattern.search(section)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _extract_kpi_rows(file_name: str, text: str) -> List[Dict[str, str]]:
    fund_name_match = re.search(r"基金名称\s+([^\n]+)", text)
    code_match = re.search(r"基金主代码\s+([0-9A-Za-z]+)", text)
    period_year_match = re.search(r"(20[0-9]{2})\s*年年度报告", text)
    company_match = re.search(r"基金管理人[:：]?\s*([^\n]+)", text)
    benchmark_match = re.search(r"业绩比较基\s*准\s+([^\n]+)", text)
    fund_type_match = re.search(r"风险收益特\s*征\s+([^\n]+)", text)

    fund_name = fund_name_match.group(1).strip() if fund_name_match else file_name
    main_code = code_match.group(1).strip() if code_match else ""
    report_period = f"{period_year_match.group(1)}-12-31" if period_year_match else ""
    company = company_match.group(1).strip() if company_match else "unknown_company"
    benchmark = benchmark_match.group(1).strip() if benchmark_match else ""
    fund_type = fund_type_match.group(1).strip() if fund_type_match else ""

    a_code, c_code = _pick_pair(text, "下属分级基金的交易代码")
    if not a_code:
        a_code = main_code
    if not c_code:
        c_code = main_code

    kpi_section = _slice_section_last(text, "3.1 主要会计数据和财务指标", "3.2 基金净值表现")
    if not kpi_section:
        kpi_section = text

    a_units, c_units = _pick_pair(text, "报告期末下属分级基金的份额")
    a_nav_total, c_nav_total = _pick_pair_regex(kpi_section, r"期末基\s*金资\s*产\s*净值")
    a_unit_nav, c_unit_nav = _pick_pair_regex(kpi_section, r"期末基\s*金份\s*额\s*净值")
    a_realized, c_realized = _pick_pair_regex(kpi_section, r"本期已\s*实现\s*收\s*益")
    a_profit, c_profit = _pick_pair_regex(kpi_section, r"本期\s*利\s*润")
    class_perf = extract_class_growth_benchmark(text, fund_name)
    a_growth, a_bench = class_perf.get("A", ("", ""))
    c_growth, c_bench = class_perf.get("C", ("", ""))

    rows = [
        {
            "source_file": file_name,
            "fund_name": fund_name,
            "company": company,
            "report_period": report_period,
            "share_class": "A",
            "fund_code": a_code,
            "fund_type": fund_type,
            "benchmark": benchmark,
            "fund_units_total": a_units,
            "fund_nav_total": a_nav_total,
            "unit_nav": a_unit_nav,
            "realized_income": a_realized,
            "period_profit": a_profit,
            "unit_nav_growth_rate_1y": a_growth,
            "benchmark_return_rate_1y": a_bench,
        },
        {
            "source_file": file_name,
            "fund_name": fund_name,
            "company": company,
            "report_period": report_period,
            "share_class": "C",
            "fund_code": c_code,
            "fund_type": fund_type,
            "benchmark": benchmark,
            "fund_units_total": c_units,
            "fund_nav_total": c_nav_total,
            "unit_nav": c_unit_nav,
            "realized_income": c_realized,
            "period_profit": c_profit,
            "unit_nav_growth_rate_1y": c_growth,
            "benchmark_return_rate_1y": c_bench,
        },
    ]

    return [row for row in rows if any(str(v).strip() for k, v in row.items() if k not in {"source_file", "share_class", "fund_name"})]


def extract_pdf_kpi_rows(file_path: Path) -> List[Dict[str, str]]:
    try:
        text = _read_pdf_text(file_path)
        return _extract_kpi_rows(file_path.name, text)
    except Exception:
        return []


def _extract_top_holdings(file_name: str, text: str) -> List[Dict[str, str]]:
    section = _slice_section(
        text,
        "8.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细",
        ["8.4 报告期内股票投资组合的重大变动", "8.4.1"],
    )
    if not section:
        return []

    pattern = re.compile(
        r"^\s*(\d+)\s+([0-9A-Za-z]{4,6})\s+([^\s]+)\s+([0-9,]+)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s*$",
        flags=re.MULTILINE,
    )
    rows = []
    for m in pattern.finditer(section):
        rank = int(m.group(1))
        if rank > 20:
            continue
        rows.append(
            {
                "source_file": file_name,
                "rank": rank,
                "stock_code": m.group(2),
                "stock_name": m.group(3),
                "shares": m.group(4),
                "market_value": m.group(5),
                "nav_ratio_pct": m.group(6),
            }
        )
    return rows


def _extract_industry_allocation(file_name: str, text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    cn_section = _slice_section(
        text,
        "8.2.1 报告期末按行业分类的境内股票投资组合",
        ["8.2.2 报告期末按行业分类的港股通投资股票投资组合", "8.2.2"],
    )
    if cn_section:
        cn_pattern = re.compile(
            r"^\s*[A-Z]\s+([^\s]+)\s+([0-9,\.-]+)\s+([0-9\.-]+)\s*$",
            flags=re.MULTILINE,
        )
        for m in cn_pattern.finditer(cn_section):
            rows.append(
                {
                    "source_file": file_name,
                    "market": "CN",
                    "industry": m.group(1),
                    "market_value": m.group(2),
                    "nav_ratio_pct": m.group(3),
                }
            )

    hk_section = _slice_section(
        text,
        "8.2.2 报告期末按行业分类的港股通投资股票投资组合",
        ["8.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细", "8.3"],
    )
    if hk_section:
        hk_pattern = re.compile(
            r"^\s*([^\d\s][^\n\r]{0,30}?)\s+([0-9,\.-]+)\s+([0-9\.-]+)\s*$",
            flags=re.MULTILINE,
        )
        for m in hk_pattern.finditer(hk_section):
            industry = m.group(1).strip()
            if industry in {"行业类别", "合计", "注：以上分类采用全球行业分类标准（GICS）。"}:
                continue
            rows.append(
                {
                    "source_file": file_name,
                    "market": "HK",
                    "industry": industry,
                    "market_value": m.group(2),
                    "nav_ratio_pct": m.group(3),
                }
            )

    return rows


def _extract_balance_sheet(file_name: str, text: str) -> List[Dict[str, str]]:
    section = _slice_section_last(text, "7.1 资产负债表", "7.2 利润表")
    if not section:
        return []
    fund_prefix = _fund_title_prefix(text)

    rows: List[Dict[str, str]] = []
    pattern = re.compile(
        r"^\s*([^\n\d][^\n]{0,60}?)\s+([\-]?[0-9,]+\.[0-9]+|-)\s+([\-]?[0-9,]+\.[0-9]+|-)\s*$",
        flags=re.MULTILINE,
    )

    skip_keywords = {
        "单位：人民币元",
        "项 目",
        "资产",
        "负债和净资产",
        "会计主体",
        "报告截止日",
    }

    for match in pattern.finditer(section):
        item = match.group(1).strip()
        if any(key in item for key in skip_keywords):
            continue
        if _is_fund_title_row(item, fund_prefix) or item.startswith("注："):
            continue
        rows.append(
            {
                "source_file": file_name,
                "item": item,
                "current_period": match.group(2),
                "prior_period": match.group(3),
            }
        )
    return rows


def _extract_income_statement(file_name: str, text: str) -> List[Dict[str, str]]:
    section = _slice_section_last(text, "7.2 利润表", "7.3 净资产变动表")
    if not section:
        return []
    fund_prefix = _fund_title_prefix(text)

    rows: List[Dict[str, str]] = []
    pattern = re.compile(
        r"^\s*([^\n]{2,80}?)\s+(?:7\.[0-9\.]+\s+)?([\-]?[0-9,]+\.[0-9]+|-)\s+([\-]?[0-9,]+\.[0-9]+|-)\s*$",
        flags=re.MULTILINE,
    )

    skip_keywords = {
        "单位：人民币元",
        "项 目",
        "本期",
        "上年度可比期间",
        "会计主体",
        "本报告期",
    }

    for match in pattern.finditer(section):
        item = re.sub(r"\s+", "", match.group(1).strip())
        if any(key in item for key in skip_keywords):
            continue
        if _is_fund_title_row(item, fund_prefix) or item.startswith("注："):
            continue
        rows.append(
            {
                "source_file": file_name,
                "item": item,
                "current_period": match.group(2),
                "prior_period": match.group(3),
            }
        )
    return rows


def _extract_net_asset_change(file_name: str, text: str) -> List[Dict[str, str]]:
    section = _slice_section_last(text, "7.3 净资产变动表", "7.4 报表附注")
    if not section:
        return []
    fund_prefix = _fund_title_prefix(text)

    rows: List[Dict[str, str]] = []
    period_tag = "current"
    pattern = re.compile(
        r"^\s*([^\n]{2,80}?)\s+([\-]?[0-9,]+\.[0-9]+|-)\s+([\-]?[0-9,]+\.[0-9]+|-)\s+([\-]?[0-9,]+\.[0-9]+|-)\s*$",
        flags=re.MULTILINE,
    )

    for line in section.split("\n"):
        clean_line = line.strip()
        if "上年度可比期间" in clean_line:
            period_tag = "prior"

        match = pattern.match(clean_line)
        if not match:
            continue

        item = re.sub(r"\s+", "", match.group(1).strip())
        if item in {"项目", "本期", "上年度可比期间"}:
            continue
        if _is_fund_title_row(item, fund_prefix) or item.startswith("注："):
            continue

        rows.append(
            {
                "source_file": file_name,
                "table_period": period_tag,
                "item": item,
                "paid_in_capital": match.group(2),
                "undistributed_profit": match.group(3),
                "total_net_assets": match.group(4),
            }
        )
    return rows


def extract_pdf_detail_tables(input_path: Path) -> Dict[str, pd.DataFrame]:
    files = _collect_pdf_files(input_path)
    kpi_rows: List[Dict[str, str]] = []
    holdings_rows: List[Dict[str, str]] = []
    industry_rows: List[Dict[str, str]] = []
    balance_rows: List[Dict[str, str]] = []
    income_rows: List[Dict[str, str]] = []
    net_asset_rows: List[Dict[str, str]] = []

    for file in files:
        try:
            text = _read_pdf_text(file)
            kpi_rows.extend(_extract_kpi_rows(file.name, text))
            holdings_rows.extend(_extract_top_holdings(file.name, text))
            industry_rows.extend(_extract_industry_allocation(file.name, text))
            balance_rows.extend(_extract_balance_sheet(file.name, text))
            income_rows.extend(_extract_income_statement(file.name, text))
            net_asset_rows.extend(_extract_net_asset_change(file.name, text))
        except Exception:
            continue

    tables: Dict[str, pd.DataFrame] = {}
    if kpi_rows:
        tables["pdf_kpi_by_class"] = pd.DataFrame(kpi_rows)
    if holdings_rows:
        tables["pdf_top_holdings"] = pd.DataFrame(holdings_rows).sort_values(["source_file", "rank"])
    if industry_rows:
        tables["pdf_industry_allocation"] = pd.DataFrame(industry_rows)
    if balance_rows:
        tables["pdf_fin_balance"] = pd.DataFrame(balance_rows)
    if income_rows:
        tables["pdf_fin_income"] = pd.DataFrame(income_rows)
    if net_asset_rows:
        tables["pdf_fin_net_asset"] = pd.DataFrame(net_asset_rows)

    return tables
