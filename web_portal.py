from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
import re
import shutil
import time
import uuid

import pandas as pd
from flask import Flask, abort, redirect, render_template, request, send_file, url_for

if getattr(sys, "frozen", False):
    # PyInstaller onefile mode: keep run artifacts next to the exe, not in the temp extraction dir
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

from src.datamind.comparison import (
    EXTRACTED_FILE,
    build_comparison,
    list_run_dirs,
    read_run_meta,
    write_run_meta,
)
from src.datamind.pipeline import run_pipeline
from src.datamind.selected_analysis import (
    build_template_analysis,
    load_selected_tables,
    write_template_analysis_report,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "output" / "web_runs"
UPLOAD_ROOT = BASE_DIR / "data" / "web_uploads"
ALLOWED_UPLOAD_EXT = {".xml", ".xbrl"}


def _safe_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def _is_valid_run_id(run_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]+", run_id))


def _sheet_preview(path: Path, sheet_names: list[str], limit: int = 30) -> list[dict[str, object]]:
    previews: list[dict[str, object]] = []
    with pd.ExcelFile(path) as xls:
        for sheet in sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            preview_df = df.head(limit).fillna("")
            previews.append(
                {
                    "sheet": sheet,
                    "rows": int(len(df)),
                    "cols": int(len(df.columns)),
                    "columns": [str(c) for c in preview_df.columns],
                    "data": preview_df.astype(str).values.tolist(),
                }
            )
    return previews


def _analysis_dimension_blocks(
    analysis_tables: dict[str, pd.DataFrame],
    charts_by_dim: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    name_map = {
        "d1_scale_trend": "规模变化趋势",
        "d1_company_compare": "同公司规模对比",
        "d1_scale_ranking": "规模排名",
        "d1_scale_concentration": "规模集中度",
        "d1_scale_attribution": "规模变动归因",
        "d2_stage_returns": "分阶段收益率",
        "d2_excess_returns": "超额收益",
        "d2_risk_return": "收益风险评估",
        "d2_peer_ranking": "同类业绩排名",
        "d2_cumulative_perf": "累计业绩",
        "d3_asset_structure": "资产结构",
        "d3_industry_distribution": "行业分布",
        "d3_top10_holdings": "前十大持仓",
        "d3_top10_concentration": "重仓集中度",
        "d3_bond_type": "债券品种配置",
        "d4_profitability": "盈利能力",
        "d4_fee_structure": "费用结构",
        "d4_profit_to_scale": "净收益规模比",
        "d4_net_flow": "申赎净额",
        "d5_company_scale": "公司规模对比",
        "d5_peer_performance": "同类业绩对比",
        "d5_style_scatter": "风格散点",
        "d5_scale_perf_matrix": "规模业绩矩阵",
        "d5_quarter_track": "季度追踪",
    }
    mapping = [
        ("d1", "d1_", "维度1：管理规模"),
        ("d2", "d2_", "维度2：业绩表现"),
        ("d3", "d3_", "维度3：资产配置"),
        ("d5", "d5_", "维度4：竞品对标"),
    ]
    blocks: list[dict[str, object]] = []
    for dim_key, prefix, title in mapping:
        tables = []
        for name, df in analysis_tables.items():
            if not name.startswith(prefix):
                continue
            preview_df = df.head(30).fillna("")
            tables.append(
                {
                    "name": name,
                    "display_name": name_map.get(name, name.replace("_", " ")),
                    "rows": int(len(df)),
                    "cols": int(len(df.columns)),
                    "columns": [str(c) for c in preview_df.columns],
                    "data": preview_df.astype(str).values.tolist(),
                }
            )
        blocks.append(
            {
                "dim": dim_key,
                "title": title,
                "tables": tables,
                "charts": charts_by_dim.get(dim_key, []),
            }
        )
    return blocks


def _to_float(value: object) -> float:
    text = str(value or "").strip().replace(",", "")
    if text in {"", "-", "--", "missing", "missingb"}:
        return 0.0
    if text.endswith("%"):
        text = text[:-1]
        return float(text) / 100.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _num_list(series: pd.Series, scale: float = 1.0) -> list[float]:
    return [float(_to_float(v) * scale) for v in series.tolist()]


def _build_chart(
    chart_id: str,
    dim: str,
    title: str,
    chart_type: str,
    labels: list[str],
    values: list[float],
    label: str,
) -> dict[str, object]:
    return {
        "id": chart_id,
        "dim": dim,
        "title": title,
        "type": chart_type,
        "labels": labels,
        "values": values,
        "label": label,
    }


def _build_charts_by_dimension(analysis_tables: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, object]]]:
    chart_index = 0

    def next_id() -> str:
        nonlocal chart_index
        chart_index += 1
        return f"chart_{chart_index}"

    grouped: dict[str, list[dict[str, object]]] = {"d1": [], "d2": [], "d3": [], "d5": []}

    # d1: 6 charts
    d1 = analysis_tables.get("d1_scale_trend", pd.DataFrame())
    if not d1.empty and {"阶段", "基金资产净值"}.issubset(d1.columns):
        grouped["d1"].append(
            _build_chart(next_id(), "d1", "单只基金规模变化趋势", "line", [str(x) for x in d1["阶段"]], _num_list(d1["基金资产净值"]), "基金资产净值")
        )
    d1_cmp = analysis_tables.get("d1_company_compare", pd.DataFrame())
    if not d1_cmp.empty and {"基金名称", "期末资产净值"}.issubset(d1_cmp.columns):
        labels = [str(x) for x in d1_cmp["基金名称"]]
        vals = _num_list(d1_cmp["期末资产净值"])
        grouped["d1"].append(_build_chart(next_id(), "d1", "同一公司多只基金规模对比", "bar", labels, vals, "期末资产净值"))
        grouped["d1"].append(_build_chart(next_id(), "d1", "不同公司同类基金规模对比", "bar", labels, vals, "期末资产净值"))
    d1_rank = analysis_tables.get("d1_scale_ranking", pd.DataFrame())
    if not d1_rank.empty and {"基金名称", "期末资产净值"}.issubset(d1_rank.columns):
        grouped["d1"].append(
            _build_chart(next_id(), "d1", "规模排名", "bar", [str(x) for x in d1_rank["基金名称"]], _num_list(d1_rank["期末资产净值"]), "期末资产净值")
        )
    d1_con = analysis_tables.get("d1_scale_concentration", pd.DataFrame())
    if not d1_con.empty and {"指标", "数值"}.issubset(d1_con.columns):
        grouped["d1"].append(_build_chart(next_id(), "d1", "规模集中度", "pie", [str(x) for x in d1_con["指标"]], _num_list(d1_con["数值"]), "集中度"))
    d1_attr = analysis_tables.get("d1_scale_attribution", pd.DataFrame())
    if not d1_attr.empty and {"因子", "数值"}.issubset(d1_attr.columns):
        grouped["d1"].append(_build_chart(next_id(), "d1", "规模变动归因", "bar", [str(x) for x in d1_attr["因子"]], _num_list(d1_attr["数值"]), "金额"))

    # d2: 5 charts
    d2_stage = analysis_tables.get("d2_stage_returns", pd.DataFrame())
    if not d2_stage.empty and {"阶段", "净值增长率"}.issubset(d2_stage.columns):
        grouped["d2"].append(_build_chart(next_id(), "d2", "各阶段收益率对比", "bar", [str(x) for x in d2_stage["阶段"]], _num_list(d2_stage["净值增长率"], 100), "净值增长率(%)"))
    d2_ex = analysis_tables.get("d2_excess_returns", pd.DataFrame())
    if not d2_ex.empty and {"阶段", "超额收益"}.issubset(d2_ex.columns):
        grouped["d2"].append(_build_chart(next_id(), "d2", "超额收益分析", "bar", [str(x) for x in d2_ex["阶段"]], _num_list(d2_ex["超额收益"], 100), "超额收益(%)"))
    d2_risk = analysis_tables.get("d2_risk_return", pd.DataFrame())
    if not d2_risk.empty and {"基金", "收益率", "波动率"}.issubset(d2_risk.columns):
        points = [{"x": _to_float(vx), "y": _to_float(vy)} for vx, vy in zip(d2_risk["波动率"], d2_risk["收益率"]) ]
        grouped["d2"].append({"id": next_id(), "dim": "d2", "title": "收益-风险综合评估", "type": "scatter", "points": points, "label": "收益率"})
    d2_rank = analysis_tables.get("d2_peer_ranking", pd.DataFrame())
    if not d2_rank.empty and {"基金", "同期收益率"}.issubset(d2_rank.columns):
        grouped["d2"].append(_build_chart(next_id(), "d2", "同类基金业绩排名", "bar", [str(x) for x in d2_rank["基金"]], _num_list(d2_rank["同期收益率"], 100), "同期收益率(%)"))

    # d3: 5 charts
    d3_alloc = analysis_tables.get("d3_asset_structure", pd.DataFrame())
    if not d3_alloc.empty and {"资产类别", "占比"}.issubset(d3_alloc.columns):
        labels = [str(x) for x in d3_alloc["资产类别"]]
        values = _num_list(d3_alloc["占比"], 100)
        grouped["d3"].append(_build_chart(next_id(), "d3", "大类资产配置结构", "pie", labels, values, "占比(%)"))
        grouped["d3"].append(_build_chart(next_id(), "d3", "资产配置变化趋势(当前样本快照)", "bar", labels, values, "占比(%)"))
    d3_ind = analysis_tables.get("d3_industry_distribution", pd.DataFrame())
    if not d3_ind.empty and {"行业类别", "占净值比例"}.issubset(d3_ind.columns):
        labels = [str(x) for x in d3_ind["行业类别"]][:20]
        values = _num_list(d3_ind["占净值比例"].head(20), 100)
        grouped["d3"].append(_build_chart(next_id(), "d3", "行业配置分布", "bar", labels, values, "占净值比例(%)"))
    d3_top = analysis_tables.get("d3_top10_holdings", pd.DataFrame())
    if not d3_top.empty and {"股票/债券名称", "占基金资产净值比例"}.issubset(d3_top.columns):
        grouped["d3"].append(_build_chart(next_id(), "d3", "前十大重仓股占比", "bar", [str(x) for x in d3_top["股票/债券名称"]], _num_list(d3_top["占基金资产净值比例"], 100), "占净值比例(%)"))
    # d5: 5 charts
    d5_comp = analysis_tables.get("d5_company_scale", pd.DataFrame())
    if not d5_comp.empty and {"公司", "公司总规模"}.issubset(d5_comp.columns):
        grouped["d5"].append(_build_chart(next_id(), "d5", "头部公司规模对比", "bar", [str(x) for x in d5_comp["公司"]], _num_list(d5_comp["公司总规模"]), "公司总规模"))
    d5_perf = analysis_tables.get("d5_peer_performance", pd.DataFrame())
    if not d5_perf.empty and {"基金", "收益率_过去1年", "收益率_过去3年", "收益率_过去5年"}.issubset(d5_perf.columns):
        row = d5_perf.iloc[0]
        grouped["d5"].append(
            _build_chart(
                next_id(),
                "d5",
                "同类产品业绩对比",
                "radar",
                ["过去1年", "过去3年", "过去5年"],
                [_to_float(row["收益率_过去1年"]) * 100, _to_float(row["收益率_过去3年"]) * 100, _to_float(row["收益率_过去5年"]) * 100],
                str(row.get("基金", "样本基金")),
            )
        )
    d5_style = analysis_tables.get("d5_style_scatter", pd.DataFrame())
    if not d5_style.empty and {"股票占比", "收益率", "基金", "规模"}.issubset(d5_style.columns):
        scatter_points = []
        bubble_points = []
        for _, row in d5_style.iterrows():
            x = _to_float(row["股票占比"]) * 100
            y = _to_float(row["收益率"]) * 100
            r = max(6.0, min(24.0, (_to_float(row["规模"]) / 1e9) * 3.5))
            scatter_points.append({"x": x, "y": y})
            bubble_points.append({"x": x, "y": y, "r": r})
        grouped["d5"].append({"id": next_id(), "dim": "d5", "title": "资产配置风格对比", "type": "scatter", "points": scatter_points, "label": "收益率(%)"})
        grouped["d5"].append({"id": next_id(), "dim": "d5", "title": "规模-业绩矩阵", "type": "bubble", "points": bubble_points, "label": "规模权重"})
    d5_track = analysis_tables.get("d5_quarter_track", pd.DataFrame())
    if not d5_track.empty and {"对象", "变化率"}.issubset(d5_track.columns):
        grouped["d5"].append(_build_chart(next_id(), "d5", "季度变动追踪", "line", [str(x) for x in d5_track["对象"]], _num_list(d5_track["变化率"], 100), "变化率(%)"))

    return grouped


def _render_analysis_context(
    run_id: str,
    cleaned: pd.DataFrame,
    analysis_tables: dict[str, pd.DataFrame],
    extracted_file: Path,
) -> dict[str, object]:
    extraction_sheet_names = [
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
    ]

    extraction_previews = _sheet_preview(extracted_file, extraction_sheet_names)
    charts_by_dim = _build_charts_by_dimension(analysis_tables)
    analysis_blocks = _analysis_dimension_blocks(analysis_tables, charts_by_dim)
    chart_cards = [chart for charts in charts_by_dim.values() for chart in charts]

    summary = {
        "records": int(len(cleaned)),
        "funds": int(cleaned["fund_name"].nunique()) if not cleaned.empty else 0,
        "companies": int(cleaned["company"].nunique()) if not cleaned.empty else 0,
    }
    return {
        "run_id": run_id,
        "summary": summary,
        "extraction_previews": extraction_previews,
        "analysis_blocks": analysis_blocks,
        "chart_cards": chart_cards,
    }


def _analysis_blocks_for_run(run_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    tables = load_selected_tables(run_dir / EXTRACTED_FILE)
    analysis_tables = build_template_analysis(tables)
    charts_by_dim = _build_charts_by_dimension(analysis_tables)
    blocks = _analysis_dimension_blocks(analysis_tables, charts_by_dim)
    chart_cards = [chart for charts in charts_by_dim.values() for chart in charts]
    meta = read_run_meta(run_dir)
    return blocks, chart_cards, meta


def _sidebar_runs(active_run_id: str | None = None) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for run_dir in list_run_dirs(OUTPUT_ROOT):
        meta = read_run_meta(run_dir)
        runs.append(
            {
                "run_id": str(meta.get("run_id")),
                "fund_name": str(meta.get("fund_name") or meta.get("run_id")),
                "company": str(meta.get("company") or "未知公司"),
                "report_period": str(meta.get("report_period") or ""),
                "generated_at": str(meta.get("generated_at") or ""),
                "active": run_dir.name == active_run_id,
            }
        )
    return runs


def _rmtree_with_retry(path: Path, attempts: int = 3, delay: float = 0.3) -> None:
    # Transient locks (AV scan, lagging GC handles) usually clear within a moment.
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except OSError as ex:
            last_error = ex
            time.sleep(delay * (attempt + 1))
    assert last_error is not None
    raise last_error


def create_app() -> Flask:
    app = Flask(__name__)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("index.html", sidebar_runs=_sidebar_runs())

    @app.post("/run")
    def run_job():
        report_url = str(request.form.get("report_url", "")).strip()
        upload = request.files.get("xml_file")

        if not report_url and (upload is None or not upload.filename):
            return render_template("index.html", sidebar_runs=_sidebar_runs(), error="请至少输入一个URL，或上传一个XML/XBRL文件。")

        run_id = _safe_run_id()
        run_dir = OUTPUT_ROOT / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        input_dir: Path | None = None
        input_url: str | None = report_url or None
        source_label = report_url if report_url else (upload.filename if upload is not None else "")

        if upload is not None and upload.filename:
            suffix = Path(upload.filename).suffix.lower()
            if suffix not in ALLOWED_UPLOAD_EXT:
                return render_template("index.html", sidebar_runs=_sidebar_runs(), error="仅支持上传 .xml 或 .xbrl 文件。")
            upload_dir = UPLOAD_ROOT / run_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            upload_path = upload_dir / Path(upload.filename).name
            upload.save(upload_path)
            input_dir = upload_dir

        extracted_file = run_dir / EXTRACTED_FILE
        brief_file = run_dir / "extracted_11tables.md"
        analysis_file = run_dir / "analysis_4dims.xlsx"

        try:
            cleaned = run_pipeline(
                input_dir=input_dir,
                input_url=input_url,
                output_excel=extracted_file,
                output_markdown=brief_file,
                include_raw_html_tables=False,
            )
            selected_tables = load_selected_tables(extracted_file)
            analysis_tables = build_template_analysis(selected_tables)
            write_template_analysis_report(analysis_file, analysis_tables)
        except Exception as ex:
            return render_template("index.html", sidebar_runs=_sidebar_runs(), error=f"执行失败: {ex}")

        write_run_meta(run_dir, cleaned, source=source_label)
        context = _render_analysis_context(run_id, cleaned, analysis_tables, extracted_file)

        return render_template(
            "index.html",
            sidebar_runs=_sidebar_runs(run_id),
            extracted_name=extracted_file.name,
            analysis_name=analysis_file.name,
            brief_name=brief_file.name,
            **context,
        )

    @app.get("/view/<run_id>")
    def view_run(run_id: str):
        if not _is_valid_run_id(run_id):
            abort(404)
        run_dir = OUTPUT_ROOT / run_id
        if not (run_dir / EXTRACTED_FILE).exists():
            abort(404)

        try:
            analysis_blocks, chart_cards, meta = _analysis_blocks_for_run(run_dir)
        except Exception:
            abort(404)

        analysis_name = "analysis_4dims.xlsx"
        if not (run_dir / analysis_name).exists() and (run_dir / "analysis_5dims.xlsx").exists():
            analysis_name = "analysis_5dims.xlsx"

        extraction_previews = _sheet_preview(
            run_dir / EXTRACTED_FILE,
            [
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
            ],
        )

        return render_template(
            "index.html",
            sidebar_runs=_sidebar_runs(run_id),
            run_id=run_id,
            summary={
                "records": int(meta.get("records") or 0),
                "funds": int(meta.get("funds") or 0),
                "companies": int(meta.get("companies") or 0),
            },
            extraction_previews=extraction_previews,
            analysis_blocks=analysis_blocks,
            chart_cards=chart_cards,
            extracted_name=EXTRACTED_FILE,
            analysis_name=analysis_name,
            brief_name="extracted_11tables.md",
            viewed_meta=meta,
        )

    @app.post("/delete/<run_id>")
    def delete_run(run_id: str):
        if not _is_valid_run_id(run_id):
            abort(404)
        run_dir = OUTPUT_ROOT / run_id
        if not run_dir.exists():
            abort(404)

        removed = False
        errors: list[str] = []
        try:
            _rmtree_with_retry(run_dir)
            removed = True
        except OSError as ex:
            errors.append(f"删除分析数据失败: {ex}")

        upload_dir = UPLOAD_ROOT / run_id
        if upload_dir.exists():
            try:
                _rmtree_with_retry(upload_dir)
            except OSError as ex:
                errors.append(f"删除上传文件失败: {ex}")

        if request.headers.get("X-Requested-With") == "fetch":
            if removed:
                return {"ok": True, "run_id": run_id}
            return {"ok": False, "run_id": run_id, "error": "；".join(errors) or "删除失败，文件可能被占用。"}, 500

        if removed:
            return redirect(url_for("index"))

        # Files likely locked by Excel/WPS; land back on the home page with a message.
        return render_template(
            "index.html",
            sidebar_runs=_sidebar_runs(),
            error="；".join(errors) or "删除失败，文件可能被占用，请关闭相关程序后重试。",
        )

    @app.post("/delete-batch")
    def delete_batch():
        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get("runs") if isinstance(payload, dict) else None
        if not isinstance(raw_ids, list):
            return {"ok": False, "error": "请求格式错误。"}, 400

        requested = []
        for item in raw_ids:
            run_id = str(item).strip()
            if _is_valid_run_id(run_id) and run_id not in requested:
                requested.append(run_id)

        deleted: list[str] = []
        failed: list[dict[str, str]] = []
        for run_id in requested:
            run_dir = OUTPUT_ROOT / run_id
            if not run_dir.exists():
                failed.append({"run_id": run_id, "error": "不存在"})
                continue
            try:
                _rmtree_with_retry(run_dir)
            except OSError as ex:
                failed.append({"run_id": run_id, "error": str(ex)})
                continue
            upload_dir = UPLOAD_ROOT / run_id
            if upload_dir.exists():
                try:
                    _rmtree_with_retry(upload_dir)
                except OSError:
                    pass
            deleted.append(run_id)

        if not requested:
            return {"ok": False, "deleted": [], "failed": [], "error": "未选择要删除的记录。"}, 400

        return {"ok": not failed, "deleted": deleted, "failed": failed}

    @app.get("/compare")
    def compare():
        selected = request.args.get("runs", "")
        selected_ids = [x.strip() for x in selected.split(",") if x.strip() and _is_valid_run_id(x.strip())]
        valid_ids = [d.name for d in list_run_dirs(OUTPUT_ROOT)]
        selected_ids = [x for x in selected_ids if x in valid_ids]

        comparison = None
        error = None
        if len(selected_ids) >= 2:
            try:
                comparison = build_comparison([OUTPUT_ROOT / rid for rid in selected_ids])
            except Exception as ex:
                error = f"对比失败: {ex}"
                comparison = None
        elif selected_ids:
            error = "请至少选择 2 个分析结果进行对比。"

        chart_cards = comparison["chart_cards"] if comparison else []

        return render_template(
            "index.html",
            sidebar_runs=_sidebar_runs(),
            compare_mode=True,
            selected_runs=selected_ids,
            comparison=comparison,
            compare_error=error,
            chart_cards=chart_cards,
        )

    @app.get("/download/<run_id>/<kind>")
    def download(run_id: str, kind: str):
        if not _is_valid_run_id(run_id):
            abort(404)
        run_dir = OUTPUT_ROOT / run_id
        if not run_dir.exists():
            abort(404)

        mapping = {
            "extracted": run_dir / EXTRACTED_FILE,
            "analysis": run_dir / "analysis_4dims.xlsx",
            "brief": run_dir / "extracted_11tables.md",
        }
        if kind == "analysis" and not mapping["analysis"].exists():
            # runs created before the 4-dimension rename stored analysis_5dims.xlsx
            mapping["analysis"] = run_dir / "analysis_5dims.xlsx"
        target = mapping.get(kind)
        if target is None or not target.exists():
            abort(404)
        return send_file(target, as_attachment=True, download_name=target.name)

    @app.template_filter("download_link")
    def download_link_filter(value: str) -> str:
        return value

    return app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DataMind web portal")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address; use 0.0.0.0 to allow access from phones on the same network",
    )
    parser.add_argument("--port", type=int, default=8787, help="Port (default 8787)")
    args = parser.parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)
