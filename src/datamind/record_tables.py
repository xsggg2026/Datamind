from __future__ import annotations

from typing import Dict, List

import pandas as pd

MISSING = "missing"

_LABEL_COLUMNS = ["字段名", "数值", "来源表", "来源标签"]

_TOP10_COLUMNS = [
    "持仓排名",
    "股票/债券代码",
    "股票/债券名称",
    "持仓数量",
    "公允价值",
    "占基金资产净值比例",
]

_INDUSTRY_COLUMNS = ["行业类别", "行业公允价值", "占净值比例"]


def _clean_text(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if text == "" or text.lower() == "nan":
        return MISSING
    return text


def _metric_rows(pairs: List[tuple[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for name, value in pairs:
        rows.append(
            {
                "字段名": name,
                "数值": _clean_text(value),
                "来源表": "record",
                "来源标签": "record",
            }
        )
    return rows


def _metric_table(rows: List[Dict[str, object]], label_header: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=_LABEL_COLUMNS)
    if label_header and not frame.empty:
        frame = frame.rename(columns={"字段名": label_header})
    return frame


def _empty_table(columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def synthesize_selected_tables(cleaned: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Build the 11-table schema directly from cleaned XBRL/XML records.

    URL reports carry the full 92-field schema from the HTML page; uploaded
    XBRL files only expose core fields, so uncovered sheets stay empty and
    downstream analysis treats those values as missing.
    """
    if cleaned is None or cleaned.empty:
        first: Dict[str, object] = {}
        nav_total: float = 0.0
    else:
        first = cleaned.iloc[0].to_dict()
        nav_series = pd.to_numeric(cleaned.get("fund_nav_total"), errors="coerce")
        nav_total = float(nav_series.fillna(0).sum()) if nav_series is not None else 0.0

    basic = _metric_table(
        _metric_rows(
            [
                ("基金名称", first.get("fund_name")),
                ("基金管理人", first.get("company")),
            ]
        ),
        "基本信息项",
    )
    fin_kpi = _metric_table(
        _metric_rows(
            [
                ("本期基金份额净值增长率", first.get("unit_nav_growth_rate")),
                ("期末基金资产净值", nav_total),
                ("期末基金份额净值", first.get("unit_nav")),
            ]
        ),
        "财务指标项",
    )
    nav_perf = _metric_table(
        _metric_rows(
            [
                ("过去3个月净值增长率", MISSING),
                ("过去6个月净值增长率", MISSING),
                ("过去1年净值增长率", first.get("unit_nav_growth_rate")),
                ("过去3年净值增长率", MISSING),
                ("过去5年净值增长率", MISSING),
                ("同期业绩比较基准收益率", first.get("benchmark_return_rate")),
            ]
        ),
        "净值表现项",
    )
    net_asset = _metric_table(
        _metric_rows(
            [
                ("期初基金净值", MISSING),
                ("期末基金净值", nav_total),
            ]
        ),
        "净资产变动项目",
    )
    portfolio = _metric_table(
        _metric_rows(
            [
                ("权益投资占净值比例", first.get("equity_ratio")),
                ("固定收益投资占净值比例", first.get("bond_ratio")),
                ("银行存款和结算备付金占比", first.get("cash_ratio")),
            ]
        ),
        "投资组合项目",
    )

    tables: Dict[str, pd.DataFrame] = {
        "表01_基本信息": basic,
        "表02_主要财务指标": fin_kpi,
        "表03_净值表现": nav_perf,
        "表04_资产负债表": _metric_table([], "资产负债项目"),
        "表05_利润表": _metric_table([], "利润项目"),
        "表06_净资产变动表": net_asset,
        "表07_投资组合报告": portfolio,
        "表08_前十大持仓": _empty_table(_TOP10_COLUMNS),
        "表09_行业配置": _empty_table(_INDUSTRY_COLUMNS),
        "表10_基金持有人结构": _metric_table([], "持有人结构项"),
        "表11_新发与募集信息": _metric_table([], "募集信息项"),
    }
    return tables
