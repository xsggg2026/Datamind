from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from .models import FundRecord
from .pdf_tables import extract_class_growth_benchmark, extract_pdf_kpi_rows


FIELD_REGEX: Dict[str, List[str]] = {
    "company": [
        r"(?:基金管理人|管理人|公司名称)[:：]\s*([^\n\r]+)",
        r"(?:Company|Manager)\s*[:：]\s*([^\n\r]+)",
    ],
    "fund_name": [
        r"(?:基金名称|产品名称)[:：]\s*([^\n\r]+)",
        r"(?:Fund\s*Name|Product\s*Name)\s*[:：]\s*([^\n\r]+)",
    ],
    "fund_code": [
        r"(?:基金主代码|基金代码|主代码)[:：]\s*([A-Za-z0-9]+)",
        r"(?:Fund\s*Code|Main\s*Code)\s*[:：]\s*([A-Za-z0-9]+)",
    ],
    "report_period": [
        r"(?:报告期|报告日期|截至日期)[:：]\s*([^\n\r]+)",
        r"(?:Report\s*Period|As\s*of\s*Date)\s*[:：]\s*([^\n\r]+)",
    ],
    "fund_type": [
        r"(?:基金类型|产品类型)[:：]\s*([^\n\r]+)",
        r"(?:Fund\s*Type|Category)\s*[:：]\s*([^\n\r]+)",
    ],
    "benchmark": [
        r"(?:业绩比较基准)[:：]\s*([^\n\r]+)",
        r"(?:Performance\s*Benchmark|Benchmark)\s*[:：]\s*([^\n\r]+)",
    ],
    "strategy": [
        r"(?:投资策略|策略)[:：]\s*([^\n\r]+)",
        r"(?:Investment\s*Strategy|Strategy)\s*[:：]\s*([^\n\r]+)",
    ],
    "fund_nav_total": [
        r"(?:基金资产净值|基金净资产|净资产规模)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Total\s*Net\s*Asset|Fund\s*NAV)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "fund_units_total": [
        r"(?:报告期末基金份额总额|基金份额总额)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Total\s*Fund\s*Units|Total\s*Shares)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "unit_nav": [
        r"(?:期末基金份额净值|基金份额净值)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Unit\s*NAV|NAV\s*Per\s*Unit)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "unit_nav_growth_rate": [
        r"(?:份额净值增长率|净值增长率|回报率)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Unit\s*NAV\s*Growth\s*Rate|Return\s*Rate)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "benchmark_return_rate": [
        r"(?:业绩比较基准收益率)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Benchmark\s*Return\s*Rate)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "equity_ratio": [
        r"(?:股票资产占比|权益占比|股票比例)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Equity\s*Ratio|Stock\s*Ratio)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "bond_ratio": [
        r"(?:债券资产占比|固收占比|债券比例)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Bond\s*Ratio|Fixed\s*Income\s*Ratio)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
    "cash_ratio": [
        r"(?:现金占比|现金及等价物占比|货币资金占比)[:：]\s*([0-9,\.\(\)\-%]+)",
        r"(?:Cash\s*Ratio|Cash\s*Allocation)\s*[:：]\s*([0-9,\.\(\)\-%]+)",
    ],
}


def _normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _normalize_inline(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _pick_first(text: str, patterns: List[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _line_values_after_label(full_text: str, label: str) -> List[str]:
    lines = full_text.split("\n")
    values: List[str] = []
    number_pattern = r"-?[0-9][0-9,]*(?:\.[0-9]+)?%?"

    for index, line in enumerate(lines):
        compact = _normalize_inline(line)
        if _normalize_inline(label) in compact:
            candidates = re.findall(number_pattern, line)
            if len(candidates) >= 2:
                return candidates

            merged = line
            for look_ahead in range(1, 4):
                if index + look_ahead >= len(lines):
                    break
                merged += " " + lines[index + look_ahead]
            candidates = re.findall(number_pattern, merged)
            if len(candidates) >= 2:
                return candidates
            values.extend(candidates)

    return values


def _pick_class_pair(full_text: str, label: str) -> Tuple[str, str]:
    candidates = _line_values_after_label(full_text, label)
    if len(candidates) >= 2:
        return candidates[0], candidates[1]
    if len(candidates) == 1:
        return candidates[0], ""
    return "", ""


def _extract_field(text: str, patterns: List[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def parse_pdf_file(file_path: Path) -> List[FundRecord]:
    kpi_rows = extract_pdf_kpi_rows(file_path)
    if kpi_rows:
        records: List[FundRecord] = []
        for row in kpi_rows:
            records.append(
                FundRecord(
                    company=str(row.get("company", "unknown_company")),
                    fund_name=str(row.get("fund_name", "") or file_path.stem),
                    fund_code=str(row.get("fund_code", "")),
                    report_period=str(row.get("report_period", "")),
                    share_class=str(row.get("share_class", "ALL")),
                    fund_type=str(row.get("fund_type", "")),
                    benchmark=str(row.get("benchmark", "")),
                    strategy="",
                    fund_nav_total=str(row.get("fund_nav_total", "0")),
                    fund_units_total=str(row.get("fund_units_total", "0")),
                    unit_nav=str(row.get("unit_nav", "0")),
                    unit_nav_growth_rate=str(row.get("unit_nav_growth_rate_1y", "0")),
                    benchmark_return_rate=str(row.get("benchmark_return_rate_1y", "0")),
                    equity_ratio="0",
                    bond_ratio="0",
                    cash_ratio="0",
                    source_file=file_path.name,
                )
            )
        if records:
            return records

    reader = PdfReader(str(file_path))
    full_text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        full_text_parts.append(page_text)
    full_text = _normalize_text("\n".join(full_text_parts))

    values = {field: _extract_field(full_text, patterns) for field, patterns in FIELD_REGEX.items()}

    fund_name = values.get("fund_name", "") or _pick_first(full_text, [r"基金名称\s+([^\n\r]+)"])
    company = values.get("company", "") or _pick_first(full_text, [r"基金管理人\s+([^\n\r]+)"])
    fund_code = values.get("fund_code", "") or _pick_first(full_text, [r"基金主代码\s+([0-9A-Za-z]+)"])
    fund_type = values.get("fund_type", "") or _pick_first(full_text, [r"风险收益特\s*征\s+([^\n\r]+)"])
    benchmark = values.get("benchmark", "") or _pick_first(full_text, [r"业绩比较基\s*准\s+([^\n\r]+)"])
    report_period = values.get("report_period", "")
    if not report_period:
        year = _pick_first(full_text, [r"(20[0-9]{2})\s*年年度报告"])
        report_period = f"{year}-12-31" if year else ""

    a_units, c_units = _pick_class_pair(full_text, "报告期末下属分级基金的份额")
    a_nav_total, c_nav_total = _pick_class_pair(full_text, "期末基金资产净值")
    a_unit_nav, c_unit_nav = _pick_class_pair(full_text, "期末基金份额净值")
    class_perf = extract_class_growth_benchmark(full_text, fund_name)
    a_growth, a_bench = class_perf.get("A", ("", ""))
    c_growth, c_bench = class_perf.get("C", ("", ""))

    equity_ratio = _pick_first(full_text, [r"权益投资\s+[0-9,\.\-]+\s+([0-9\.\-]+)"])
    bond_ratio = _pick_first(full_text, [r"固定收益投资\s+[0-9,\.\-]+\s+([0-9\.\-]+)"])
    cash_ratio = _pick_first(full_text, [r"银行存款和结算备付金合计\s+[0-9,\.\-]+\s+([0-9\.\-]+)"])

    a_code, c_code = _pick_class_pair(full_text, "下属分级基金的交易代码")
    if not a_code:
        a_code = fund_code
    if not c_code:
        c_code = fund_code

    fallback_name = file_path.stem
    base_strategy = values.get("strategy", "")

    def build_record(share_class: str) -> FundRecord:
        if share_class == "A":
            return FundRecord(
                company=company or "unknown_company",
                fund_name=fund_name or fallback_name,
                fund_code=a_code,
                report_period=report_period,
                share_class="A",
                fund_type=fund_type,
                benchmark=benchmark,
                strategy=base_strategy,
                fund_nav_total=a_nav_total or values.get("fund_nav_total", "0"),
                fund_units_total=a_units or values.get("fund_units_total", "0"),
                unit_nav=a_unit_nav or values.get("unit_nav", "0"),
                unit_nav_growth_rate=a_growth or values.get("unit_nav_growth_rate", "0"),
                benchmark_return_rate=a_bench or values.get("benchmark_return_rate", "0"),
                equity_ratio=equity_ratio or values.get("equity_ratio", "0"),
                bond_ratio=bond_ratio or values.get("bond_ratio", "0"),
                cash_ratio=cash_ratio or values.get("cash_ratio", "0"),
                source_file=file_path.name,
            )

        return FundRecord(
            company=company or "unknown_company",
            fund_name=fund_name or fallback_name,
            fund_code=c_code,
            report_period=report_period,
            share_class="C",
            fund_type=fund_type,
            benchmark=benchmark,
            strategy=base_strategy,
            fund_nav_total=c_nav_total or values.get("fund_nav_total", "0"),
            fund_units_total=c_units or values.get("fund_units_total", "0"),
            unit_nav=c_unit_nav or values.get("unit_nav", "0"),
            unit_nav_growth_rate=c_growth or values.get("unit_nav_growth_rate", "0"),
            benchmark_return_rate=c_bench or values.get("benchmark_return_rate", "0"),
            equity_ratio=equity_ratio or values.get("equity_ratio", "0"),
            bond_ratio=bond_ratio or values.get("bond_ratio", "0"),
            cash_ratio=cash_ratio or values.get("cash_ratio", "0"),
            source_file=file_path.name,
        )

    has_split = any([a_units, c_units, a_nav_total, c_nav_total, a_unit_nav, c_unit_nav])
    if has_split:
        return [build_record("A"), build_record("C")]

    share_class = "ALL"
    if re.search(r"\bA\b|A类", fallback_name, flags=re.IGNORECASE):
        share_class = "A"
    if re.search(r"\bC\b|C类", fallback_name, flags=re.IGNORECASE):
        share_class = "C"

    return [
        FundRecord(
            company=company or "unknown_company",
            fund_name=fund_name or fallback_name,
            fund_code=fund_code,
            report_period=report_period,
            share_class=share_class,
            fund_type=fund_type,
            benchmark=benchmark,
            strategy=base_strategy,
            fund_nav_total=values.get("fund_nav_total", "0"),
            fund_units_total=values.get("fund_units_total", "0"),
            unit_nav=values.get("unit_nav", "0"),
            unit_nav_growth_rate=values.get("unit_nav_growth_rate", "0"),
            benchmark_return_rate=values.get("benchmark_return_rate", "0"),
            equity_ratio=equity_ratio or values.get("equity_ratio", "0"),
            bond_ratio=bond_ratio or values.get("bond_ratio", "0"),
            cash_ratio=cash_ratio or values.get("cash_ratio", "0"),
            source_file=file_path.name,
        )
    ]
