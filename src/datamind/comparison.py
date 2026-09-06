from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .selected_analysis import build_template_analysis, load_selected_tables

MISSING = "missing"
META_FILE = "meta.json"
EXTRACTED_FILE = "extracted_11tables.xlsx"

STAGE_ORDER = ["过去3个月", "过去6个月", "过去1年", "过去3年", "过去5年", "过去7年", "过去10年"]


def _num_or_none(value: object) -> Optional[float]:
    text = str(value if value is not None else "").strip().replace(",", "")
    if text in {"", "-", "--", MISSING, "missingb", "nan", "None"}:
        return None
    if text.endswith("%"):
        text = text[:-1]
        try:
            return float(text) / 100.0
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _fmt_amount(value: Optional[float]) -> str:
    return f"{value:,.2f}" if value is not None else MISSING


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value * 100:.4f}%" if value is not None else MISSING


def _df_rows(df: pd.DataFrame) -> List[Dict[str, object]]:
    if df is None or df.empty:
        return []
    return df.fillna("").to_dict("records")


def write_run_meta(run_dir: Path, cleaned: pd.DataFrame, source: str) -> Dict[str, object]:
    fund_name = ""
    company = ""
    report_period = ""
    if cleaned is not None and not cleaned.empty:
        first = cleaned.iloc[0]
        fund_name = str(first.get("fund_name", "") or "")
        company = str(first.get("company", "") or "")
        report_period = str(first.get("report_period", "") or "")

    meta: Dict[str, object] = {
        "run_id": run_dir.name,
        "fund_name": fund_name or run_dir.name,
        "company": company or "未知公司",
        "report_period": report_period,
        "source": source,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "records": int(len(cleaned)) if cleaned is not None else 0,
        "funds": int(cleaned["fund_name"].nunique()) if cleaned is not None and not cleaned.empty else 0,
        "companies": int(cleaned["company"].nunique()) if cleaned is not None and not cleaned.empty else 0,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / META_FILE).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _basic_info_from_extracted(extracted: Path) -> Dict[str, str]:
    info = {"fund_name": "", "company": "", "report_period": ""}
    if not extracted.exists():
        return info
    try:
        # pd.ExcelFile keeps the workbook handle open until closed; leaving it to
        # the GC delays release on Windows and makes an immediate rmtree fail.
        with pd.ExcelFile(extracted) as xls:
            sheet = None
            for name in ("表01_基本信息", "table01_basic_info"):
                if name in xls.sheet_names:
                    sheet = name
                    break
            if sheet is None:
                return info
            df = pd.read_excel(xls, sheet_name=sheet)
        if df.empty or len(df.columns) < 2:
            return info
        label_col = str(df.columns[0])
        value_col = "数值" if "数值" in df.columns else str(df.columns[1])

        def pick(label: str) -> str:
            row = df[df[label_col].astype(str).str.strip() == label]
            if row.empty:
                return ""
            return str(row.iloc[0][value_col]).strip()

        info["fund_name"] = pick("基金名称")
        info["company"] = pick("基金管理人")
        return info
    except Exception:
        return info


def _stats_from_extracted(extracted: Path) -> Dict[str, int]:
    """Approximate run stats from the stored 11-table workbook (for runs without meta.json)."""
    stats = {"records": 0, "funds": 0, "companies": 0}
    if not extracted.exists():
        return stats
    try:
        with pd.ExcelFile(extracted) as xls:
            sheet = next((s for s in ("表01_基本信息", "table01_basic_info") if s in xls.sheet_names), None)
            if sheet is None:
                return stats
            df = pd.read_excel(xls, sheet_name=sheet)
        if df.empty:
            return stats
        label_col = str(df.columns[0])
        labels = df[label_col].astype(str).str.strip()
        has_value = df.notna().any(axis=1)
        stats["records"] = int((labels != "nan").sum())
        stats["funds"] = 1 if (labels == "基金名称").any() else 0
        stats["companies"] = 1 if (labels == "基金管理人").any() else 0
        return stats
    except Exception:
        return stats


def read_run_meta(run_dir: Path) -> Dict[str, object]:
    meta_path = run_dir / META_FILE
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("fund_name"):
                return data
        except Exception:
            pass

    info = _basic_info_from_extracted(run_dir / EXTRACTED_FILE)
    stats = _stats_from_extracted(run_dir / EXTRACTED_FILE)
    stamp = run_dir.name[:15].replace("_", " ") if len(run_dir.name) >= 15 else ""
    meta = {
        "run_id": run_dir.name,
        "fund_name": info["fund_name"] or run_dir.name,
        "company": info["company"] or "未知公司",
        "report_period": info["report_period"],
        "source": "",
        "generated_at": stamp,
        "records": stats["records"],
        "funds": stats["funds"],
        "companies": stats["companies"],
    }
    try:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return meta


def list_run_dirs(runs_root: Path) -> List[Path]:
    if not runs_root.exists():
        return []
    runs = []
    for child in sorted(runs_root.iterdir(), reverse=True):
        if child.is_dir() and (child / EXTRACTED_FILE).exists():
            runs.append(child)
    return runs


def load_run_analysis(run_dir: Path):
    tables = load_selected_tables(run_dir / EXTRACTED_FILE)
    analysis = build_template_analysis(tables)
    return analysis, read_run_meta(run_dir)


def _entry_label(meta: Dict[str, object]) -> str:
    fund = str(meta.get("fund_name") or "")
    period = str(meta.get("report_period") or "")
    stamp = str(meta.get("generated_at") or "")[:16]
    label = fund or str(meta.get("run_id") or "")
    suffix = " / ".join(x for x in (period, stamp) if x)
    return f"{label}（{suffix}）" if suffix else label


def build_comparison(run_dirs: List[Path]) -> Dict[str, object]:
    entries: List[Dict[str, object]] = []
    for run_dir in run_dirs:
        try:
            analysis, meta = load_run_analysis(run_dir)
        except Exception:
            continue
        entries.append({"run_id": run_dir.name, "meta": meta, "tables": analysis})

    if not entries:
        raise ValueError("所选分析结果均无法读取 11 表数据。")

    chart_index = 0

    def next_id() -> str:
        nonlocal chart_index
        chart_index += 1
        return f"cmpchart_{chart_index}"

    sections: List[Dict[str, object]] = []
    chart_cards: List[Dict[str, object]] = []

    def add_section(key: str, title: str, note: str, columns: List[str], rows: List[Dict[str, object]], charts: List[Dict[str, object]]) -> None:
        chart_cards.extend(charts)
        sections.append(
            {
                "key": key,
                "title": title,
                "note": note,
                "columns": columns,
                "rows": rows,
                "chart_ids": [c["id"] for c in charts],
            }
        )

    # --- 1) 基金规模对比（公司×基金，公司列 + 基金名列区分）
    scale_rows: List[Dict[str, object]] = []
    for entry in entries:
        for row in _df_rows(entry["tables"].get("d1_company_compare", pd.DataFrame())):
            scale_rows.append(
                {
                    "run_id": entry["run_id"],
                    "公司": str(row.get("公司", "") or MISSING),
                    "基金名称": str(row.get("基金名称", "") or MISSING),
                    "_nav": _num_or_none(row.get("期末资产净值")),
                }
            )
    scale_rows.sort(key=lambda x: -(x["_nav"] if x["_nav"] is not None else 0.0))
    add_section(
        "cmp_scale_overview",
        "基金规模对比",
        "各选中分析的基金期末资产净值对比（按规模降序；图中序号对应下表首列，公司 + 基金名区分同公司多只基金）。",
        ["序号", "公司", "基金名称", "期末资产净值(元)"],
        [
            {"序号": idx + 1, "公司": r["公司"], "基金名称": r["基金名称"], "期末资产净值(元)": _fmt_amount(r["_nav"])}
            for idx, r in enumerate(scale_rows)
        ],
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "基金规模对比(元)",
                "type": "bar",
                "labels": [str(idx + 1) for idx in range(len(scale_rows))],
                "names": [f"{r['公司']}·{r['基金名称']}" for r in scale_rows],
                "values": [r["_nav"] if r["_nav"] is not None else None for r in scale_rows],
                "label": "期末资产净值",
            }
        ],
    )

    # --- 3) 规模排名
    ranking_rows = sorted(scale_rows, key=lambda x: -(x["_nav"] if x["_nav"] is not None else 0.0))
    ranked = [
        {"排名": idx + 1, "基金名称": r["基金名称"], "公司": r["公司"], "期末资产净值(元)": _fmt_amount(r["_nav"])}
        for idx, r in enumerate(ranking_rows)
    ]
    add_section(
        "cmp_scale_ranking",
        "规模排名",
        "按期末资产净值从高到低排名。",
        ["排名", "基金名称", "公司", "期末资产净值(元)"],
        ranked,
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "规模排名(元)",
                "type": "hbar",
                "labels": [str(len(ranking_rows) - idx) for idx in range(len(ranking_rows))],
                "names": [f"{r['公司']}·{r['基金名称']}" for r in reversed(ranking_rows)],
                "values": [r["_nav"] if r["_nav"] is not None else None for r in reversed(ranking_rows)],
                "label": "期末资产净值",
            }
        ],
    )

    # --- 4) 各阶段收益率对比 & 5) 超额收益分析
    def stage_wide(table_key: str, value_col: str) -> tuple[List[Dict[str, object]], List[str], List[Dict[str, object]]]:
        per_run: Dict[str, Dict[str, Optional[float]]] = {}
        for entry in entries:
            values: Dict[str, Optional[float]] = {}
            for row in _df_rows(entry["tables"].get(table_key, pd.DataFrame())):
                stage = str(row.get("阶段", "")).strip()
                if stage in STAGE_ORDER:
                    values[stage] = _num_or_none(row.get(value_col))
            per_run[entry["run_id"]] = values
        columns = ["阶段"] + [_entry_label(e["meta"]) for e in entries]
        rows: List[Dict[str, object]] = []
        for stage in STAGE_ORDER:
            row: Dict[str, object] = {"阶段": stage}
            for entry in entries:
                row[_entry_label(entry["meta"])] = _fmt_pct(per_run[entry["run_id"]].get(stage))
            rows.append(row)
        datasets = [
            {
                "label": _entry_label(entry["meta"]),
                "values": [per_run[entry["run_id"]].get(stage) for stage in STAGE_ORDER],
            }
            for entry in entries
        ]
        return rows, columns, datasets

    stage_rows, stage_cols, stage_datasets = stage_wide("d2_stage_returns", "净值增长率")
    add_section(
        "cmp_stage_returns",
        "各阶段收益率对比",
        "各分析之间的净值增长率按相同报告阶段横向对比。",
        stage_cols,
        stage_rows,
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "各阶段收益率对比(%)",
                "type": "bar",
                "labels": STAGE_ORDER,
                "datasets": [
                    {"label": ds["label"], "values": [v * 100 if v is not None else None for v in ds["values"]]}
                    for ds in stage_datasets
                ],
                "label": "净值增长率(%)",
            }
        ],
    )

    excess_rows, excess_cols, excess_datasets = stage_wide("d2_excess_returns", "超额收益")
    add_section(
        "cmp_excess_returns",
        "超额收益分析",
        "各分析相对业绩比较基准的超额收益（基准收益率取自各分析自身的过去1年基准）。",
        excess_cols,
        excess_rows,
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "超额收益分析(%)",
                "type": "bar",
                "labels": STAGE_ORDER,
                "datasets": [
                    {"label": ds["label"], "values": [v * 100 if v is not None else None for v in ds["values"]]}
                    for ds in excess_datasets
                ],
                "label": "超额收益(%)",
            }
        ],
    )

    # --- 6) 收益-风险综合评估
    risk_rows_out: List[Dict[str, object]] = []
    risk_datasets: List[Dict[str, object]] = []
    for entry in entries:
        rows = _df_rows(entry["tables"].get("d2_risk_return", pd.DataFrame()))
        for row in rows:
            ret = _num_or_none(row.get("收益率"))
            vol = _num_or_none(row.get("波动率"))
            fund = str(row.get("基金", "") or _entry_label(entry["meta"]))
            risk_rows_out.append(
                {
                    "基金": fund,
                    "收益率": _fmt_pct(ret),
                    "波动率": _fmt_pct(vol) if vol is not None else MISSING,
                    "说明": str(row.get("说明", "") or MISSING),
                }
            )
        risk_datasets.append(
            {
                "label": _entry_label(entry["meta"]),
                "points": [{"x": (vol or 0.0) * 100, "y": (ret or 0.0) * 100} for ret, vol in
                           [(_num_or_none(r.get("收益率")), _num_or_none(r.get("波动率"))) for r in rows]],
            }
        )
    add_section(
        "cmp_risk_return",
        "收益-风险综合评估",
        "散点图每点代表一个分析；11表暂无标准差字段，波动率为占位值，待数据补充后自动生效。",
        ["基金", "收益率", "波动率", "说明"],
        risk_rows_out,
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "收益-风险综合评估(%)",
                "type": "scatter",
                "datasets": risk_datasets,
                "label": "收益率(%)",
            }
        ],
    )

    # --- 7) 同类基金业绩排名
    peer_rows: List[Dict[str, object]] = []
    for entry in entries:
        ret = None
        values = _df_rows(entry["tables"].get("d2_stage_returns", pd.DataFrame()))
        for row in values:
            if str(row.get("阶段", "")).strip() == "过去1年":
                ret = _num_or_none(row.get("净值增长率"))
                break
        peer_rows.append(
            {
                "run_id": entry["run_id"],
                "基金": str(entry["meta"].get("fund_name") or entry["run_id"]),
                "_ret": ret,
            }
        )
    peer_rows.sort(key=lambda x: -(x["_ret"] if x["_ret"] is not None else -1e18))
    peer_out = [
        {"排名": idx + 1, "基金": r["基金"], "过去1年收益率": _fmt_pct(r["_ret"])}
        for idx, r in enumerate(peer_rows)
    ]
    add_section(
        "cmp_peer_ranking",
        "同类基金业绩排名",
        "按过去1年净值增长率从高到低排名。",
        ["排名", "基金", "过去1年收益率"],
        peer_out,
        [
            {
                "id": next_id(),
                "dim": "cmp",
                "title": "同类基金业绩排名(%)",
                "type": "hbar",
                "labels": [str(len(peer_rows) - idx) for idx in range(len(peer_rows))],
                "names": [str(r["基金"]) for r in reversed(peer_rows)],
                "values": [r["_ret"] * 100 if r["_ret"] is not None else None for r in reversed(peer_rows)],
                "label": "过去1年收益率(%)",
            }
        ],
    )

    return {
        "entries": [{"meta": e["meta"], "label": _entry_label(e["meta"])} for e in entries],
        "sections": sections,
        "chart_cards": chart_cards,
    }
