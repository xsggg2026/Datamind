from __future__ import annotations

import re
import pandas as pd


def parse_numeric(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace(",", "")
    is_percent = "%" in text
    text = text.replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", "."}:
        return 0.0
    number = float(text)
    if negative:
        number = -number
    if is_percent:
        return number / 100.0
    return number


def normalize_period(period: str) -> str:
    text = str(period or "").strip()
    if not text:
        return "unknown"
    text = text.replace("/", "-").replace(".", "-")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def infer_fund_type(row: pd.Series) -> str:
    fund_type = str(row.get("fund_type", "")).strip()
    strategy = str(row.get("strategy", "")).lower()
    if fund_type:
        return fund_type
    if "equity" in strategy or "stock" in strategy:
        return "Equity"
    if "bond" in strategy or "fixed income" in strategy:
        return "Bond"
    if "money market" in strategy or "cash" in strategy:
        return "Money Market"
    return "Other"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    numeric_columns = [
        "fund_nav_total",
        "fund_units_total",
        "unit_nav",
        "unit_nav_growth_rate",
        "benchmark_return_rate",
        "equity_ratio",
        "bond_ratio",
        "cash_ratio",
    ]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].apply(parse_numeric)

    for ratio_col in ["equity_ratio", "bond_ratio", "cash_ratio"]:
        if ratio_col in df.columns:
            df[ratio_col] = df[ratio_col].clip(lower=0.0)

    df["report_period"] = df["report_period"].apply(normalize_period)
    df["fund_type"] = df.apply(infer_fund_type, axis=1)
    if "share_class" in df.columns:
        df["share_class"] = df["share_class"].fillna("").astype(str).str.strip().str.upper()
        df.loc[df["share_class"].isin(["", "NAN", "NONE"]), "share_class"] = "ALL"

    text_cols = ["company", "fund_name", "fund_code", "benchmark", "strategy", "source_file"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    dedup_subset = ["company", "fund_name", "report_period"]
    if "share_class" in df.columns:
        dedup_subset.append("share_class")
    df = df.drop_duplicates(subset=dedup_subset, keep="last")
    return df
