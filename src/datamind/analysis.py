from __future__ import annotations

from typing import Dict
import pandas as pd


def scale_ranking(df: pd.DataFrame) -> pd.DataFrame:
    table = df[["company", "fund_name", "fund_type", "report_period", "fund_nav_total"]].copy()
    table = table.sort_values("fund_nav_total", ascending=False)
    table["scale_rank"] = range(1, len(table) + 1)
    return table


def month_over_month_change(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    table = df[["company", "fund_name", "report_period", "fund_nav_total", "unit_nav_growth_rate"]].copy()
    table = table.sort_values(["fund_name", "report_period"])
    table["nav_mom_change"] = table.groupby("fund_name")["fund_nav_total"].pct_change().fillna(0.0)
    return table


def type_distribution(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("fund_type", as_index=False)
        .agg(product_count=("fund_name", "count"), total_nav=("fund_nav_total", "sum"))
        .sort_values("total_nav", ascending=False)
    )


def strategy_performance(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("strategy", as_index=False)
        .agg(
            avg_growth_rate=("unit_nav_growth_rate", "mean"),
            median_growth_rate=("unit_nav_growth_rate", "median"),
            products=("fund_name", "count"),
            total_nav=("fund_nav_total", "sum"),
        )
        .sort_values("avg_growth_rate", ascending=False)
    )


def quarterly_company_board(df: pd.DataFrame) -> pd.DataFrame:
    table = (
        df.groupby(["company", "report_period"], as_index=False)
        .agg(
            total_nav=("fund_nav_total", "sum"),
            avg_growth_rate=("unit_nav_growth_rate", "mean"),
            product_count=("fund_name", "nunique"),
        )
        .copy()
    )
    table["report_period_dt"] = pd.to_datetime(table["report_period"], errors="coerce")
    table = table.sort_values(["company", "report_period_dt", "report_period"])
    table["nav_qoq_change"] = table.groupby("company")["total_nav"].pct_change().fillna(0.0)
    return table.drop(columns=["report_period_dt"])


def product_type_trend(df: pd.DataFrame) -> pd.DataFrame:
    pivot = (
        pd.pivot_table(
            df,
            index="report_period",
            columns="fund_type",
            values="fund_nav_total",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
        .copy()
    )
    pivot["report_period_dt"] = pd.to_datetime(pivot["report_period"], errors="coerce")
    pivot = pivot.sort_values(["report_period_dt", "report_period"]).drop(columns=["report_period_dt"])
    return pivot


def company_nav_trend(df: pd.DataFrame) -> pd.DataFrame:
    pivot = (
        pd.pivot_table(
            df,
            index="report_period",
            columns="company",
            values="fund_nav_total",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
        .copy()
    )
    pivot["report_period_dt"] = pd.to_datetime(pivot["report_period"], errors="coerce")
    pivot = pivot.sort_values(["report_period_dt", "report_period"]).drop(columns=["report_period_dt"])
    return pivot


def build_analysis_tables(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {
        "scale_ranking": scale_ranking(df),
        "mom_change": month_over_month_change(df),
        "type_distribution": type_distribution(df),
        "strategy_performance": strategy_performance(df),
        "quarterly_company_board": quarterly_company_board(df),
        "product_type_trend": product_type_trend(df),
        "company_nav_trend": company_nav_trend(df),
    }
