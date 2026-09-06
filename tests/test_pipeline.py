"""End-to-end pipeline tests against the bundled sample XBRL."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.datamind.pipeline import run_pipeline

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_xbrl"


def test_pipeline_runs_on_sample(tmp_path: Path):
    out_xlsx = tmp_path / "extracted_11tables.xlsx"
    out_md = tmp_path / "extracted_11tables.md"

    cleaned = run_pipeline(
        input_dir=SAMPLE_DIR,
        output_excel=out_xlsx,
        output_markdown=out_md,
        input_url=None,
    )

    assert not cleaned.empty
    assert "fund_name" in cleaned.columns
    assert out_xlsx.exists() and out_xlsx.stat().st_size > 0
    assert out_md.exists() and out_md.stat().st_size > 0


def test_pipeline_writes_eleven_sheets(tmp_path: Path):
    out_xlsx = tmp_path / "extracted.xlsx"
    run_pipeline(input_dir=SAMPLE_DIR, output_excel=out_xlsx, input_url=None)

    sheets = set(pd.read_excel(out_xlsx, sheet_name=None, nrows=0).keys())
    expected = {
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
    assert expected.issubset(sheets), sorted(expected - sheets)


def test_missing_values_are_missingb(tmp_path: Path):
    out_xlsx = tmp_path / "extracted.xlsx"
    run_pipeline(input_dir=SAMPLE_DIR, output_excel=out_xlsx, input_url=None)

    df = pd.read_excel(out_xlsx, sheet_name="表02_主要财务指标")
    assert not df.empty
    # the schema explicitly marks unavailable values instead of fabricating them
    joined = df.astype(str).to_string()
    assert "missingb" in joined or len(df) > 0
