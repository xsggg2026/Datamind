from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
import time
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .models import FundRecord


MISSING_TOKEN = "missing"


def _metric_definitions() -> List[Dict[str, str]]:
    raw_defs: List[Tuple[int, str, str, str, str]] = [
        (1, "表1 基金基本信息", "基金名称", "JiJinMingCheng", "string"),
        (2, "表1 基金基本信息", "基金简称", "JiJinJianCheng", "string"),
        (3, "表1 基金基本信息", "基金代码", "JiJinDaiMa", "string"),
        (4, "表1 基金基本信息", "基金运作方式", "JiJinYunZuoFangShi", "string"),
        (5, "表1 基金基本信息", "基金合同生效日", "JiJinHeTongShengXiaoRi", "date"),
        (6, "表1 基金基本信息", "报告期末基金份额总额", "JiJinE", "number"),
        (7, "表1 基金基本信息", "基金管理人", "JiJinGuanLiRen", "string"),
        (8, "表1 基金基本信息", "基金托管人", "JiJinTuoGuanRen", "string"),
        (9, "表1 基金基本信息", "业绩比较基准", "YeJiBiJiaoJiZhun", "string"),
        (10, "表2 主要财务指标", "本期已实现收益", "BenQiYiShiXianShouYi", "amount"),
        (11, "表2 主要财务指标", "本期利润", "BenQiLiRun", "amount"),
        (12, "表2 主要财务指标", "加权平均基金份额本期利润", "JiaQuanPingJunJiJinEBenQiLiRun", "amount"),
        (13, "表2 主要财务指标", "本期基金份额净值增长率", "JiJinJingZhiZengZhangLv", "percent"),
        (14, "表2 主要财务指标", "期末基金资产净值", "QiMoJiJinZiChanJingZhi", "amount"),
        (15, "表2 主要财务指标", "期末基金份额净值", "QiMoJiJinEJingZhi", "amount"),
        (16, "表2 主要财务指标", "期末基金份额累计净值", "LeiJiJingZhi", "amount"),
        (17, "表2 主要财务指标", "本期基金份额收益率", "BenQiJiJinEShouYiLv", "percent"),
        (18, "表3 基金净值表现", "过去3个月净值增长率", "JingZhiZengZhangLv_3M", "percent"),
        (19, "表3 基金净值表现", "过去6个月净值增长率", "JingZhiZengZhangLv_6M", "percent"),
        (20, "表3 基金净值表现", "过去1年净值增长率", "JingZhiZengZhangLv_1Y", "percent"),
        (21, "表3 基金净值表现", "过去3年净值增长率", "JingZhiZengZhangLv_3Y", "percent"),
        (22, "表3 基金净值表现", "过去5年净值增长率", "JingZhiZengZhangLv_5Y", "percent"),
        (23, "表3 基金净值表现", "过去7年净值增长率", "JingZhiZengZhangLv_7Y", "percent"),
        (24, "表3 基金净值表现", "过去10年净值增长率", "JingZhiZengZhangLv_10Y", "percent"),
        (25, "表3 基金净值表现", "同期业绩比较基准收益率", "YeJiBiJiaoJiZhunShouYiLv", "percent"),
        (26, "表4 资产负债表", "银行存款", "YinHangCunKuan", "amount"),
        (27, "表4 资产负债表", "结算备付金", "JieSuanBeiFuJin", "amount"),
        (28, "表4 资产负债表", "存出保证金", "CunChuBaoZhengJin", "amount"),
        (29, "表4 资产负债表", "交易性金融资产", "JiaoYiXingJinRongZiChan", "amount"),
        (30, "表4 资产负债表", "股票投资", "GuPiaoTouZi", "amount"),
        (31, "表4 资产负债表", "债券投资", "ZhaiQuanTouZi", "amount"),
        (32, "表4 资产负债表", "基金投资", "JiJinTouZi", "amount"),
        (33, "表4 资产负债表", "资产支持证券", "ZiChanZhiChiZhengQuan", "amount"),
        (34, "表4 资产负债表", "买入返售金融资产", "MaiRuFanShouJinRongZiChan", "amount"),
        (35, "表4 资产负债表", "应收利息", "YingShouLiXi", "amount"),
        (36, "表4 资产负债表", "应收申购款", "YingShouShenGouKuan", "amount"),
        (37, "表4 资产负债表", "其他资产", "QiTaZiChan", "amount"),
        (38, "表4 资产负债表", "资产总计", "ZiChanZongJi", "amount"),
        (39, "表4 资产负债表", "卖出回购金融资产款", "MaiChuHuiGouJinRongZiChanKuan", "amount"),
        (40, "表4 资产负债表", "应付管理人报酬", "YingFuGuanLiRenBaoChou", "amount"),
        (41, "表4 资产负债表", "应付托管费", "YingFuTuoGuanFei", "amount"),
        (42, "表4 资产负债表", "应付交易费用", "YingFuJiaoYiFeiYong", "amount"),
        (43, "表4 资产负债表", "应付赎回款", "YingFuShuHuiKuan", "amount"),
        (44, "表4 资产负债表", "其他负债", "QiTaFuZhai", "amount"),
        (45, "表4 资产负债表", "负债总计", "FuZhaiZongJi", "amount"),
        (46, "表4 资产负债表", "所有者权益（基金净值）", "SuoYouZheQuanYi", "amount"),
        (47, "表5 利润表", "利息收入", "LiXiShouRu", "amount"),
        (48, "表5 利润表", "投资收益", "TouZiShouYi", "amount"),
        (49, "表5 利润表", "公允价值变动收益", "GongYunJiaZhiBianDongShouYi", "amount"),
        (50, "表5 利润表", "其他收入", "QiTaShouRu", "amount"),
        (51, "表5 利润表", "营业总收入", "YingYeZongShouRu", "amount"),
        (52, "表5 利润表", "管理人报酬", "GuanLiRenBaoChou", "amount"),
        (53, "表5 利润表", "托管费", "TuoGuanFei", "amount"),
        (54, "表5 利润表", "交易费用", "JiaoYiFeiYong", "amount"),
        (55, "表5 利润表", "其他费用", "QiTaFeiYong", "amount"),
        (56, "表5 利润表", "利润总额", "LiRunZongE", "amount"),
        (57, "表6 净资产变动表", "期初基金净值", "QiChuJiJinJingZhi", "amount"),
        (58, "表6 净资产变动表", "本期申购", "BenQiShenGou", "amount_or_units"),
        (59, "表6 净资产变动表", "本期赎回", "BenQiShuHui", "amount_or_units"),
        (60, "表6 净资产变动表", "本期利润分配", "BenQiLiRunFenPei", "amount"),
        (61, "表6 净资产变动表", "期末基金净值", "QiMoJiJinJingZhi", "amount"),
        (62, "表7 投资组合报告", "权益投资（股票）金额", "QuanYiTouZiJinE", "amount"),
        (63, "表7 投资组合报告", "权益投资占净值比例", "QuanYiTouZiBiLi", "percent"),
        (64, "表7 投资组合报告", "固定收益投资（债券）金额", "GuDingShouYiTouZiJinE", "amount"),
        (65, "表7 投资组合报告", "固定收益投资占净值比例", "GuDingShouYiTouZiBiLi", "percent"),
        (66, "表7 投资组合报告", "基金投资金额", "JiJinTouZiJinE", "amount"),
        (67, "表7 投资组合报告", "基金投资占净值比例", "JiJinTouZiBiLi", "percent"),
        (68, "表7 投资组合报告", "买入返售金融资产金额", "MaiRuFanShouJinE", "amount"),
        (69, "表7 投资组合报告", "买入返售占净值比例", "MaiRuFanShouBiLi", "percent"),
        (70, "表7 投资组合报告", "银行存款和结算备付金合计", "YinHangCunKuanHeJi", "amount"),
        (71, "表7 投资组合报告", "银行存款和结算备付金占比", "YinHangCunKuanBiLi", "percent"),
        (72, "表7 投资组合报告", "其他资产金额", "QiTaZiChanJinE", "amount"),
        (73, "表7 投资组合报告", "其他资产占比", "QiTaZiChanBiLi", "percent"),
        (74, "表7 投资组合报告", "资产组合合计", "ZiChanZuHeHeJi", "amount"),
        (75, "表8 前十大持仓", "持仓排名", "PaiMing", "integer"),
        (76, "表8 前十大持仓", "股票/债券代码", "ZhengQuanDaiMa", "string"),
        (77, "表8 前十大持仓", "股票/债券名称", "ZhengQuanMingCheng", "string"),
        (78, "表8 前十大持仓", "持仓数量", "ShuLiang", "number"),
        (79, "表8 前十大持仓", "公允价值", "GongYunJiaZhi", "amount"),
        (80, "表8 前十大持仓", "占基金资产净值比例", "ZhanJingZhiBiLi", "percent"),
        (81, "表9 行业配置", "行业类别", "HangYeLeiBie", "string"),
        (82, "表9 行业配置", "行业公允价值", "HangYeGongYunJiaZhi", "amount"),
        (83, "表9 行业配置", "占净值比例", "ZhanJingZhiBiLi", "percent"),
        (84, "表10 基金持有人结构", "机构投资者持有份额", "JiGouChiYouFenE", "units"),
        (85, "表10 基金持有人结构", "机构投资者持有比例", "JiGouChiYouBiLi", "percent"),
        (86, "表10 基金持有人结构", "个人投资者持有份额", "GeRenChiYouFenE", "units"),
        (87, "表10 基金持有人结构", "个人投资者持有比例", "GeRenChiYouBiLi", "percent"),
        (88, "表10 基金持有人结构", "内部持有份额", "NeiBuChiYouFenE", "units"),
        (89, "表11 新发与募集信息", "募集起始日", "MuJiQiShiRi", "date"),
        (90, "表11 新发与募集信息", "募集截止日", "MuJiJieZhiRi", "date"),
        (91, "表11 新发与募集信息", "募集份额总额", "MuJiFenEZongE", "units"),
        (92, "表11 新发与募集信息", "有效认购户数", "YouXiaoRenGouHuShu", "integer"),
    ]
    return [
        {
            "field_no": str(field_no),
            "section": section,
            "field_name": field_name,
            "xbrl_element": xbrl_element,
            "data_type": data_type,
        }
        for field_no, section, field_name, xbrl_element, data_type in raw_defs
    ]


def fetch_html(url: str, timeout: int = 25) -> str:
    headers_list = [
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        },
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        {},
    ]

    raw = b""
    last_error: Exception | None = None
    for attempt in range(1, 6):
        headers = headers_list[(attempt - 1) % len(headers_list)]
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout + attempt * 5) as resp:
                raw = resp.read()
            break
        except HTTPError as ex:
            last_error = ex
            # Retry temporary gateway/network-side errors.
            if ex.code in {429, 500, 502, 503, 504} and attempt < 5:
                time.sleep(attempt * 1.2)
                continue
            raise
        except (URLError, TimeoutError) as ex:
            last_error = ex
            if attempt < 5:
                time.sleep(attempt * 1.2)
                continue
            raise

    if not raw:
        if last_error:
            raise last_error
        raise RuntimeError("Failed to fetch HTML content")
    # CSRC pages are usually utf-8, with gb18030 fallback for compatibility.
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _strip_tags(html_text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _search_group(text: str, patterns: List[str], group: int = 1) -> str:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(group).strip()
    return ""


def _extract_report_period(text: str) -> str:
    annual_period = _search_group(
        text,
        [
            r"20\d{2}年[年度中期季]{1,2}报告\s*(20\d{2}-\d{1,2}-\d{1,2})",
            r"20\d{2}年[年度中期季]{1,2}报告\s*(20\d{2}年\d{1,2}月\d{1,2}日)",
        ],
    )
    if annual_period:
        candidate = annual_period
    else:
        candidate = _search_group(
            text,
            [
                r"(20\d{2}年\d{1,2}月\d{1,2}日)",
                r"(20\d{2}-\d{1,2}-\d{1,2})",
                r"(20\d{6})",
            ],
        )
    if "年" in candidate and "月" in candidate and "日" in candidate:
        m = re.match(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", candidate)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if re.match(r"20\d{2}-\d{1,2}-\d{1,2}", candidate):
        y, mo, d = candidate.split("-")
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    if re.match(r"20\d{6}", candidate):
        return f"{candidate[:4]}-{candidate[4:6]}-{candidate[6:8]}"
    return ""


def _extract_fund_record_from_text(text: str, source_url: str) -> FundRecord:
    fund_name = _search_group(
        text,
        [
            r"基金简称[:：]\s*([^\s]{2,80})",
            r"基金名称[:：]\s*([^\s]{2,80})",
            r"([\u4e00-\u9fa5A-Za-z0-9（）()·\-]{4,80}基金)20\d{2}年[年度中期季]{1,2}报告",
        ],
    )
    fund_code = _search_group(
        text,
        [
            r"基金主代码[:：]\s*([A-Za-z0-9]{6,12})",
            r"基金代码[:：]\s*([A-Za-z0-9]{6,12})",
        ],
    )
    if not fund_code:
        m = re.search(r"_([0-9]{6})_FB", source_url, flags=re.IGNORECASE)
        if m:
            fund_code = m.group(1)
    company = _search_group(
        text,
        [
            r"基金管理人[:：]\s*([^\s]{2,80})",
            r"管理人[:：]\s*([^\s]{2,80})",
        ],
    )
    fund_type = _search_group(
        text,
        [
            r"基金运作方式[:：]\s*([^\s]{2,40})",
            r"基金类型[:：]\s*([^\s]{2,40})",
        ],
    )

    nav_total = _search_group(
        text,
        [
            r"期末基金资产净值[:：]?\s*([0-9,\.\-]+)",
            r"基金资产净值[:：]?\s*([0-9,\.\-]+)",
        ],
    )
    units_total = _search_group(
        text,
        [
            r"期末基金份额总额[:：]?\s*([0-9,\.\-]+)",
            r"基金份额总额[:：]?\s*([0-9,\.\-]+)",
        ],
    )
    unit_nav = _search_group(
        text,
        [
            r"期末基金份额净值[:：]?\s*([0-9,\.\-]+)",
            r"基金份额净值[:：]?\s*([0-9,\.\-]+)",
        ],
    )
    growth = _search_group(
        text,
        [
            r"本期份额净值增长率[:：]?\s*([0-9,\.\-]+%?)",
            r"净值增长率[:：]?\s*([0-9,\.\-]+%?)",
        ],
    )
    benchmark_return = _search_group(
        text,
        [
            r"业绩比较基准收益率[:：]?\s*([0-9,\.\-]+%?)",
            r"基准收益率[:：]?\s*([0-9,\.\-]+%?)",
        ],
    )

    if growth and "%" not in growth:
        growth = f"{growth}%"
    if benchmark_return and "%" not in benchmark_return:
        benchmark_return = f"{benchmark_return}%"

    report_period = _extract_report_period(text)

    return FundRecord(
        company=company or "unknown_company",
        fund_name=fund_name or "unknown_fund",
        fund_code=fund_code,
        report_period=report_period,
        share_class="ALL",
        fund_type=fund_type,
        benchmark="",
        strategy="",
        fund_nav_total=nav_total or "0",
        fund_units_total=units_total or "0",
        unit_nav=unit_nav or "0",
        unit_nav_growth_rate=growth or "0",
        benchmark_return_rate=benchmark_return or "0",
        equity_ratio="0",
        bond_ratio="0",
        cash_ratio="0",
        source_file=source_url,
    )


class _SimpleHTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._table: List[List[str]] = []
        self._row: List[str] = []
        self._cell_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        tag = tag.lower()
        if tag == "table":
            self._in_table = True
            self._table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_chunks = []
        elif self._in_cell and tag == "br":
            self._cell_chunks.append("\\n")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._in_cell:
            self._in_cell = False
            value = unescape("".join(self._cell_chunks))
            value = re.sub(r"\s+", " ", value).strip()
            self._row.append(value)
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if any(cell for cell in self._row):
                self._table.append(self._row)
        elif tag == "table" and self._in_table:
            self._in_table = False
            if self._table:
                self.tables.append(self._table)


def _table_to_df(table: List[List[str]]) -> pd.DataFrame:
    if not table:
        return pd.DataFrame()

    width = max(len(r) for r in table)
    rows = [r + [""] * (width - len(r)) for r in table]
    header = rows[0]
    unique_non_empty = len({x for x in header if x})
    if unique_non_empty >= max(2, width // 2):
        body = rows[1:] if len(rows) > 1 else []
        columns = [col if col else f"col_{i+1}" for i, col in enumerate(header)]
        return pd.DataFrame(body, columns=columns)

    columns = [f"col_{i+1}" for i in range(width)]
    return pd.DataFrame(rows, columns=columns)


def _non_empty_cells(df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        for val in row:
            if str(val).strip() and str(val).strip().lower() != "nan":
                count += 1
    return count


def _classify_table_name(df: pd.DataFrame) -> str:
    content = " ".join(str(x) for x in df.fillna("").to_numpy().flatten())
    headers = " ".join(str(x) for x in df.columns)
    compact = _normalize_label(content + " " + headers)

    if "基金名称" in compact and "基金主代码" in compact:
        return "html_fund_profile"
    if "投资目标" in compact and "业绩比较基准" in compact:
        return "html_invest_profile"
    if "期间数据和指标" in compact and "本期已实现收益" in compact:
        return "html_kpi_history"
    if "阶段" in compact and "份额净值增长率" in compact:
        return "html_nav_performance"
    if "股票名称" in compact and "占基金资产净值比例" in compact:
        return "html_top_holdings"
    if "债券名称" in compact and "占基金资产净值比例" in compact:
        return "html_top_bond_holdings"
    if "行业类别" in compact and "占基金资产净值比例" in compact:
        return "html_industry_allocation"
    if "净资产合计" in compact and "本期增减变动额" in compact:
        return "html_fin_net_asset"
    if "资产" in compact and "本期末" in compact and "上年度末" in compact:
        return "html_fin_balance"
    if "项目" in compact and "本期" in compact and "上年度可比期间" in compact:
        return "html_fin_income"
    if "持有人结构" in compact and "机构投资者" in compact and "个人投资者" in compact:
        return "html_holder_structure"
    if "募集起始日" in compact or "募集截止日" in compact:
        return "html_fundraising"
    return ""


def _unique_sheet_name(existing: Dict[str, pd.DataFrame], base: str) -> str:
    if base not in existing:
        return base
    idx = 2
    while f"{base}_{idx}" in existing:
        idx += 1
    return f"{base}_{idx}"


def parse_html_url(url: str) -> List[FundRecord]:
    html_text = fetch_html(url)
    text = _strip_tags(html_text)
    record = _extract_fund_record_from_text(text, source_url=url)

    meaningful = any(
        str(getattr(record, field)).strip() not in {"", "0", "0.0"}
        for field in ["fund_code", "report_period", "fund_nav_total", "unit_nav"]
    )
    if not meaningful:
        return []
    return [record]


def _normalize_label(text: str) -> str:
    t = str(text or "")
    t = t.replace("（", "(").replace("）", ")")
    t = re.sub(r"\s+", "", t)
    return t


def _parse_number(text: str) -> float:
    value = str(text or "").strip().replace(",", "")
    if not value or value in {"-", "--"}:
        return 0.0
    if value.endswith("%"):
        value = value[:-1]
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    value = re.sub(r"[^0-9.\-]", "", value)
    if value in {"", "-", "."}:
        return 0.0
    number = float(value)
    return -number if negative else number


def _find_value_by_keywords(df: pd.DataFrame, keywords: List[str]) -> Tuple[str, str]:
    return _find_value_by_keywords_with_period(df, keywords, prefer_current=True)


def _is_current_period_header(header: str) -> bool:
    h = _normalize_label(header)
    if not h:
        return False
    return ("本期" in h or "期末" in h or "当期" in h) and not _is_previous_period_header(header)


def _is_previous_period_header(header: str) -> bool:
    h = _normalize_label(header)
    if not h:
        return False
    prev_tokens = ["上年度末", "上年度", "上期", "上年", "可比期间", "期初", "2024", "2023", "2022"]
    return any(tok in h for tok in prev_tokens)


def _find_value_by_keywords_with_period(
    df: pd.DataFrame,
    keywords: List[str],
    prefer_current: bool = True,
    strict_current: bool = False,
) -> Tuple[str, str]:
    normalized_keywords = [_normalize_label(k) for k in keywords]
    headers = [str(h) for h in df.columns]
    current_col_indexes = {idx for idx, h in enumerate(headers) if _is_current_period_header(h)}

    best_value = ""
    best_label = ""
    best_score = -999

    for _, row in df.fillna("").iterrows():
        cells = [str(x).strip() for x in row.tolist()]
        if not any(cells):
            continue
        label = cells[0]
        normalized_label = _normalize_label(label)
        if any(k in normalized_label for k in normalized_keywords):
            for idx, val in enumerate(cells[1:], start=1):
                # If current-period columns are identifiable, only allow values from them.
                if strict_current and current_col_indexes and idx not in current_col_indexes:
                    continue
                if not val or val in {"-", "--"}:
                    continue
                score = 0
                header = headers[idx] if idx < len(headers) else ""
                if prefer_current and _is_current_period_header(header):
                    score += 8
                if _is_previous_period_header(header):
                    score -= 8
                if "col_" in header:
                    score -= 1
                if idx == 1:
                    score += 1
                if score > best_score:
                    best_score = score
                    best_value = val
                    best_label = label

    return best_value, best_label


def _find_tables(named_tables: Dict[str, pd.DataFrame], prefix: str) -> List[Tuple[str, pd.DataFrame]]:
    matches: List[Tuple[str, pd.DataFrame]] = []
    for name, table in named_tables.items():
        if name == prefix or name.startswith(prefix + "_"):
            matches.append((name, table))
    return matches


def _find_value_from_table_group(
    named_tables: Dict[str, pd.DataFrame],
    prefix: str,
    keywords: List[str],
) -> Tuple[str, str, str]:
    best_table = ""
    best_label = ""
    best_value = ""
    best_score = -999

    for table_name, table in _find_tables(named_tables, prefix):
        value, label = _find_value_by_keywords_with_period(table, keywords, prefer_current=True)
        if not value:
            continue
        score = 0
        headers = [str(h) for h in table.columns]
        if any(_is_current_period_header(h) for h in headers):
            score += 6
        if any(_is_previous_period_header(h) for h in headers):
            score -= 2
        if table_name == prefix:
            score += 1
        if score > best_score:
            best_score = score
            best_table = table_name
            best_label = label
            best_value = value

    return best_value, best_label, best_table


def _find_table(named_tables: Dict[str, pd.DataFrame], prefix: str) -> pd.DataFrame:
    for name, table in named_tables.items():
        if name == prefix or name.startswith(prefix + "_"):
            return table
    return pd.DataFrame()


def _find_best_table(named_tables: Dict[str, pd.DataFrame], prefix: str) -> pd.DataFrame:
    candidates = _find_tables(named_tables, prefix)
    if not candidates:
        return pd.DataFrame()

    best_df = candidates[0][1]
    best_score = -999
    for _, df in candidates:
        score = 0
        headers = [str(h) for h in df.columns]
        if any(_is_current_period_header(h) for h in headers):
            score += 6
        if any(_is_previous_period_header(h) for h in headers):
            score -= 2
        score += min(len(df), 100) / 100
        if score > best_score:
            best_score = score
            best_df = df
    return best_df


def _find_primary_statement_table(named_tables: Dict[str, pd.DataFrame], prefix: str) -> pd.DataFrame:
    candidates = _find_tables(named_tables, prefix)
    if not candidates:
        return pd.DataFrame()

    best_df = pd.DataFrame()
    best_score = -999
    for _, df in candidates:
        headers = [str(h) for h in df.columns]
        header_blob = _normalize_label(" ".join(headers))
        score = 0

        if any(_is_current_period_header(h) for h in headers):
            score += 8
        if any(_is_previous_period_header(h) for h in headers):
            score += 3

        if prefix == "html_fin_balance":
            if "资产" in header_blob or "负债" in header_blob or "项目" in header_blob:
                score += 6
            if len(headers) <= 4:
                score += 4
            if len(df) >= 20:
                score += 4
        elif prefix == "html_fin_income":
            if "项目" in header_blob and "本期" in header_blob:
                score += 6
            if len(headers) <= 4:
                score += 4
            if len(df) >= 20:
                score += 4
        elif prefix == "html_fin_net_asset":
            content_blob = _normalize_label(" ".join(str(x) for x in df.fillna("").to_numpy().flatten()))
            if "净资产合计" in content_blob and "本期增减变动额" in content_blob:
                score += 8
            if len(headers) <= 6:
                score += 2
            if len(df) >= 10:
                score += 3

        score += min(len(df), 120) / 120
        if score > best_score:
            best_score = score
            best_df = df

    return best_df


def _pick_col_by_keywords(columns: List[str], keywords: List[str]) -> str:
    normalized = [(_normalize_label(c), c) for c in columns]
    key_norm = [_normalize_label(k) for k in keywords]
    for col_norm, col in normalized:
        if any(k in col_norm for k in key_norm):
            return col
    return ""


def _format_percent(numerator: str, denominator: str) -> str:
    den = _parse_number(denominator)
    if den == 0:
        return ""
    num = _parse_number(numerator)
    return f"{(num / den) * 100:.4f}%"


def _build_selected_top_holdings_df(df: pd.DataFrame) -> pd.DataFrame:
    output_cols = ["持仓排名", "股票/债券代码", "股票/债券名称", "持仓数量", "公允价值", "占基金资产净值比例"]
    if df.empty:
        return pd.DataFrame(columns=output_cols)

    columns = [str(c) for c in df.columns]
    code_col = _pick_col_by_keywords(columns, ["股票代码", "债券代码", "证券代码", "代码"])
    name_col = _pick_col_by_keywords(columns, ["股票名称", "债券名称", "证券名称", "名称"])
    qty_col = _pick_col_by_keywords(columns, ["数量", "持仓量"])
    value_col = _pick_col_by_keywords(columns, ["公允价值", "市值"])
    ratio_col = _pick_col_by_keywords(columns, ["占基金资产净值比例", "占净值比例"])

    rows = []
    rank = 1
    for _, row in df.fillna("").iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        if not name or name in {"合计", "-", "--"}:
            continue
        rows.append(
            {
                "持仓排名": rank,
                "股票/债券代码": str(row.get(code_col, "")).strip() if code_col else "",
                "股票/债券名称": name,
                "持仓数量": str(row.get(qty_col, "")).strip() if qty_col else "",
                "公允价值": str(row.get(value_col, "")).strip() if value_col else "",
                "占基金资产净值比例": str(row.get(ratio_col, "")).strip() if ratio_col else "",
            }
        )
        rank += 1
        if rank > 10:
            break
    return pd.DataFrame(rows, columns=output_cols)


def _build_selected_industry_df(df: pd.DataFrame) -> pd.DataFrame:
    output_cols = ["行业类别", "行业公允价值", "占净值比例"]
    if df.empty:
        return pd.DataFrame(columns=output_cols)

    columns = [str(c) for c in df.columns]
    industry_col = _pick_col_by_keywords(columns, ["行业类别", "行业"])
    value_col = _pick_col_by_keywords(columns, ["公允价值", "市值"])
    ratio_col = _pick_col_by_keywords(columns, ["占基金资产净值比例", "占净值比例"])

    rows = []
    for _, row in df.fillna("").iterrows():
        industry = str(row.get(industry_col, "")).strip() if industry_col else ""
        if not industry or industry in {"合计", "-", "--"}:
            continue
        rows.append(
            {
                "行业类别": industry,
                "行业公允价值": str(row.get(value_col, "")).strip() if value_col else "",
                "占净值比例": str(row.get(ratio_col, "")).strip() if ratio_col else "",
            }
        )
    return pd.DataFrame(rows, columns=output_cols)


def _extract_named_tables(url: str, max_tables: int = 500, keep_generic: bool = False) -> Dict[str, pd.DataFrame]:
    html_text = fetch_html(url)
    parser = _SimpleHTMLTableParser()
    parser.feed(html_text)

    tables: Dict[str, pd.DataFrame] = {}
    generic_idx = 1
    for raw_table in parser.tables:
        df = _table_to_df(raw_table)
        if df.empty:
            continue

        # Skip decorative layout tables with almost no information.
        if _non_empty_cells(df) < 4:
            continue
        if len(df) < 2 and len(df.columns) < 2:
            continue

        semantic_name = _classify_table_name(df)
        if semantic_name:
            name = _unique_sheet_name(tables, semantic_name)
            tables[name] = df
        else:
            if not keep_generic:
                continue
            name = f"html_table_{generic_idx:02d}"
            generic_idx += 1
            tables[name] = df
        if len(tables) >= max_tables:
            break

    return tables


def _build_selective_metrics(
    named_tables: Dict[str, pd.DataFrame],
    record: FundRecord,
) -> pd.DataFrame:
    metrics = _metric_definitions()
    values: Dict[int, Dict[str, str]] = {}

    for item in metrics:
        no = int(item["field_no"])
        values[no] = {
            "value": "",
            "source_table": "",
            "source_label": "",
        }

    def set_value(no: int, value: str, source_table: str, source_label: str) -> None:
        if value and not values[no]["value"]:
            values[no] = {
                "value": value,
                "source_table": source_table,
                "source_label": source_label,
            }

    # 1-17 from main record and fund profile / KPI tables
    set_value(1, record.fund_name, "record", "fund_name")
    set_value(3, record.fund_code, "record", "fund_code")
    set_value(4, record.fund_type, "record", "fund_type")
    set_value(6, str(record.fund_units_total), "record", "fund_units_total")
    set_value(7, record.company, "record", "company")
    set_value(9, record.benchmark, "record", "benchmark")
    set_value(13, str(record.unit_nav_growth_rate), "record", "unit_nav_growth_rate")
    set_value(14, str(record.fund_nav_total), "record", "fund_nav_total")
    set_value(15, str(record.unit_nav), "record", "unit_nav")
    if str(record.benchmark_return_rate).strip() not in {"", "0", "0.0"}:
        set_value(25, str(record.benchmark_return_rate), "record", "benchmark_return_rate")
    set_value(61, str(record.fund_nav_total), "record", "fund_nav_total")

    profile = _find_table(named_tables, "html_fund_profile")
    if not profile.empty:
        for no, keys in {
            2: ["基金简称"],
            4: ["基金运作方式"],
            5: ["基金合同生效日"],
            8: ["基金托管人"],
            9: ["业绩比较基准"],
        }.items():
            val, label = _find_value_by_keywords(profile, keys)
            set_value(no, val, "html_fund_profile", label)

    invest_profile = _find_table(named_tables, "html_invest_profile")
    if not invest_profile.empty:
        val, label = _find_value_by_keywords(invest_profile, ["业绩比较基准"])
        set_value(9, val, "html_invest_profile", label)

    kpi_history = _find_table(named_tables, "html_kpi_history")
    if not kpi_history.empty:
        for no, keys in {
            10: ["本期已实现收益"],
            11: ["本期利润"],
            12: ["加权平均基金份额本期利润"],
            13: ["本期基金份额净值增长率"],
            16: ["期末基金份额累计净值"],
            17: ["本期基金份额收益率"],
        }.items():
            val, label = _find_value_by_keywords(kpi_history, keys)
            set_value(no, val, "html_kpi_history", label)

    nav_perf = _find_table(named_tables, "html_nav_performance")
    if not nav_perf.empty:
        stage_to_field = {
            "过去三个月": 18,
            "过去3个月": 18,
            "过去六个月": 19,
            "过去6个月": 19,
            "过去一年": 20,
            "过去1年": 20,
            "过去三年": 21,
            "过去3年": 21,
            "过去五年": 22,
            "过去5年": 22,
            "过去七年": 23,
            "过去7年": 23,
            "过去十年": 24,
            "过去10年": 24,
        }
        stage_col = str(nav_perf.columns[0])
        growth_col = next((c for c in nav_perf.columns if "份额净值增长率" in str(c)), None)
        benchmark_col = next((c for c in nav_perf.columns if "业绩比较基准收益率" in str(c)), None)
        for _, row in nav_perf.fillna("").iterrows():
            stage = str(row.get(stage_col, "")).strip()
            target_field = stage_to_field.get(stage)
            if target_field and growth_col is not None:
                set_value(target_field, str(row.get(growth_col, "")).strip(), "html_nav_performance", stage)
            if stage in {"过去一年", "过去1年"} and benchmark_col is not None:
                set_value(25, str(row.get(benchmark_col, "")).strip(), "html_nav_performance", stage)

    balance = _find_primary_statement_table(named_tables, "html_fin_balance")
    if not balance.empty:
        for no, keys in {
            27: ["结算备付金"],
            28: ["存出保证金"],
            29: ["交易性金融资产"],
            30: ["股票投资"],
            31: ["债券投资"],
            32: ["基金投资"],
            33: ["资产支持证券"],
            34: ["买入返售金融资产"],
            35: ["应收利息"],
            36: ["应收申购款"],
            37: ["其他资产"],
            38: ["资产总计"],
            39: ["卖出回购金融资产款"],
            40: ["应付管理人报酬"],
            41: ["应付托管费"],
            42: ["应付交易费用"],
            43: ["应付赎回款"],
            44: ["其他负债"],
            45: ["负债总计", "负债合计"],
            46: ["所有者权益", "基金净值", "净资产合计"],
        }.items():
            val, label = _find_value_by_keywords_with_period(
                balance,
                keys,
                prefer_current=True,
                strict_current=True,
            )
            set_value(no, val, "html_fin_balance", label)

        cash, cash_label = _find_value_by_keywords_with_period(
            balance,
            ["货币资金"],
            prefer_current=True,
            strict_current=True,
        )
        if cash:
            set_value(26, cash, "html_fin_balance", cash_label)

    income = _find_primary_statement_table(named_tables, "html_fin_income")
    if not income.empty:
        for no, keys in {
            47: ["利息收入"],
            48: ["投资收益"],
            49: ["公允价值变动收益"],
            50: ["其他收入"],
            51: ["营业总收入"],
            52: ["管理人报酬"],
            53: ["托管费"],
            54: ["交易费用"],
            55: ["其他费用"],
            56: ["利润总额", "本期利润"],
        }.items():
            val, label = _find_value_by_keywords_with_period(income, keys, prefer_current=True)
            set_value(no, val, "html_fin_income", label)

    net_asset = _find_primary_statement_table(named_tables, "html_fin_net_asset")
    if not net_asset.empty:
        for no, keys in {
            57: ["本期期初净资产", "上期期末净资产"],
            58: ["基金申购款"],
            59: ["基金赎回款"],
            60: ["利润分配"],
            61: ["本期期末净资产"],
        }.items():
            val, label = _find_value_by_keywords_with_period(net_asset, keys, prefer_current=True)
            set_value(no, val, "html_fin_net_asset", label)

    # Derived portfolio metrics from balance + net asset
    nav_value = values[61]["value"] or values[14]["value"]
    if values[30]["value"]:
        set_value(62, values[30]["value"], "derived", "股票投资")
        set_value(63, _format_percent(values[30]["value"], nav_value), "derived", "股票投资/期末基金净值")
    if values[31]["value"]:
        set_value(64, values[31]["value"], "derived", "债券投资")
        set_value(65, _format_percent(values[31]["value"], nav_value), "derived", "债券投资/期末基金净值")
    if values[32]["value"]:
        set_value(66, values[32]["value"], "derived", "基金投资")
        set_value(67, _format_percent(values[32]["value"], nav_value), "derived", "基金投资/期末基金净值")
    if values[34]["value"]:
        set_value(68, values[34]["value"], "derived", "买入返售金融资产")
        set_value(69, _format_percent(values[34]["value"], nav_value), "derived", "买入返售金融资产/期末基金净值")

    cash_total = _parse_number(values[26]["value"]) + _parse_number(values[27]["value"])
    if cash_total > 0:
        set_value(70, f"{cash_total:.2f}", "derived", "银行存款+结算备付金")
        set_value(71, _format_percent(f"{cash_total}", nav_value), "derived", "(银行存款+结算备付金)/期末基金净值")
    if values[37]["value"]:
        set_value(72, values[37]["value"], "derived", "其他资产")
        set_value(73, _format_percent(values[37]["value"], nav_value), "derived", "其他资产/期末基金净值")
    if values[38]["value"]:
        set_value(74, values[38]["value"], "derived", "资产总计")

    top_holdings_table = _find_table(named_tables, "html_top_holdings")
    if top_holdings_table.empty:
        top_holdings_table = _find_table(named_tables, "html_top_bond_holdings")
    selected_top = _build_selected_top_holdings_df(top_holdings_table)
    if not selected_top.empty:
        first = selected_top.iloc[0]
        set_value(75, "1-10", "selected_top10_holdings", "top rows")
        set_value(76, str(first.get("股票/债券代码", "")), "selected_top10_holdings", "first row")
        set_value(77, str(first.get("股票/债券名称", "")), "selected_top10_holdings", "first row")
        set_value(78, str(first.get("持仓数量", "")), "selected_top10_holdings", "first row")
        set_value(79, str(first.get("公允价值", "")), "selected_top10_holdings", "first row")
        set_value(80, str(first.get("占基金资产净值比例", "")), "selected_top10_holdings", "first row")

    industry_table = _find_table(named_tables, "html_industry_allocation")
    selected_industry = _build_selected_industry_df(industry_table)
    if not selected_industry.empty:
        tmp = selected_industry.copy()
        tmp["_v"] = tmp["行业公允价值"].apply(_parse_number)
        top_industry = tmp.sort_values("_v", ascending=False).iloc[0]
        set_value(81, str(top_industry.get("行业类别", "")), "selected_industry", "max fair value")
        set_value(82, str(top_industry.get("行业公允价值", "")), "selected_industry", "max fair value")
        set_value(83, str(top_industry.get("占净值比例", "")), "selected_industry", "max fair value")

    holder_table = _find_table(named_tables, "html_holder_structure")
    if not holder_table.empty:
        holder_rows = holder_table.fillna("").astype(str)
        if len(holder_rows) >= 1:
            last = holder_rows.iloc[-1].tolist()
            if len(last) >= 6:
                set_value(84, str(last[2]).strip(), "html_holder_structure", "机构投资者持有份额")
                set_value(85, str(last[3]).strip(), "html_holder_structure", "机构投资者持有比例")
                set_value(86, str(last[4]).strip(), "html_holder_structure", "个人投资者持有份额")
                set_value(87, str(last[5]).strip(), "html_holder_structure", "个人投资者持有比例")

    rows = []
    for item in metrics:
        no = int(item["field_no"])
        captured = values[no]
        rows.append(
            {
                "field_no": no,
                "section": item["section"],
                "field_name": item["field_name"],
                "xbrl_element_ref": item["xbrl_element"],
                "data_type": item["data_type"],
                "value": captured["value"],
                "source_table": captured["source_table"],
                "source_label": captured["source_label"],
                "status": "hit" if captured["value"] else "missing",
            }
        )
    return pd.DataFrame(rows)


def _build_coverage(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["section", "total_fields", "hit_fields", "coverage"])
    summary = (
        df.groupby("section", as_index=False)
        .agg(total_fields=("field_no", "count"), hit_fields=("status", lambda s: int((s == "hit").sum())))
    )
    summary["coverage"] = summary.apply(
        lambda r: f"{(r['hit_fields'] / r['total_fields']) * 100:.1f}%" if r["total_fields"] else "0.0%",
        axis=1,
    )
    return summary


def _metrics_table_by_range(metrics_df: pd.DataFrame, start_no: int, end_no: int) -> pd.DataFrame:
    cols = [
        "field_name",
        "value",
        "source_table",
        "source_label",
    ]
    out = metrics_df[(metrics_df["field_no"] >= start_no) & (metrics_df["field_no"] <= end_no)][
        ["field_no"] + cols
    ].copy()
    out = out.sort_values("field_no").reset_index(drop=True)
    out = out.drop(columns=["field_no"])
    out = out.rename(
        columns={
            "field_name": "字段名",
            "value": "数值",
            "source_table": "来源表",
            "source_label": "来源标签",
        }
    )
    return out


def _is_missing_value(value: object) -> bool:
    text = str(value).strip()
    return text == "" or text.lower() == "nan"


def _finalize_metric_table_values(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    value_col = "数值" if "数值" in out.columns else ("value" if "value" in out.columns else "")
    if value_col:
        out[value_col] = out[value_col].apply(lambda x: MISSING_TOKEN if _is_missing_value(x) else x)
    if "status" in out.columns and value_col:
        out["status"] = out[value_col].apply(lambda x: "missing" if str(x) == MISSING_TOKEN else "hit")
    return out


def _rename_metric_label_column(table: pd.DataFrame, new_label: str) -> pd.DataFrame:
    out = table.copy()
    if "字段名" in out.columns:
        out = out.rename(columns={"字段名": new_label})
    return out


def _find_metric_label_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        cs = str(c)
        if cs.endswith("项") or cs.endswith("项目") or cs.endswith("名称") or cs == "字段名":
            return cs
    return str(df.columns[0]) if len(df.columns) > 0 else ""


def _find_metric_value_col(df: pd.DataFrame) -> str:
    if "数值" in df.columns:
        return "数值"
    for c in df.columns:
        if str(c).endswith("数值"):
            return str(c)
    return "数值"


def _ensure_nonempty_domain_table(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([{col: MISSING_TOKEN for col in columns}], columns=columns)
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = MISSING_TOKEN
    out = out[columns]
    out = out.fillna(MISSING_TOKEN)
    return out


def extract_html_detail_tables(
    url: str,
    max_tables: int = 500,
    include_raw_tables: bool = False,
) -> Dict[str, pd.DataFrame]:
    named_tables = _extract_named_tables(
        url,
        max_tables=max_tables,
        keep_generic=include_raw_tables,
    )
    records = parse_html_url(url)
    record = records[0] if records else _extract_fund_record_from_text(_strip_tags(fetch_html(url)), source_url=url)

    selected_metrics = _build_selective_metrics(named_tables, record)
    selected_coverage = _build_coverage(selected_metrics)

    top_holdings_table = _find_table(named_tables, "html_top_holdings")
    if top_holdings_table.empty:
        top_holdings_table = _find_table(named_tables, "html_top_bond_holdings")
    selected_top_holdings = _build_selected_top_holdings_df(top_holdings_table)

    industry_table = _find_table(named_tables, "html_industry_allocation")
    selected_industry = _build_selected_industry_df(industry_table)

    holder_table = _find_table(named_tables, "html_holder_structure")
    fundraising_table = _find_table(named_tables, "html_fundraising")
    if holder_table.empty:
        holder_table = pd.DataFrame(
            columns=["机构投资者持有份额", "机构投资者持有比例", "个人投资者持有份额", "个人投资者持有比例", "内部持有份额"]
        )
    if fundraising_table.empty:
        fundraising_table = pd.DataFrame(columns=["募集起始日", "募集截止日", "募集份额总额", "有效认购户数"])

    if not holder_table.empty and len(holder_table) >= 1:
        holder_last = holder_table.fillna("").astype(str).iloc[-1].tolist()
        holder_value_map = {
            "机构投资者持有份额": holder_last[2] if len(holder_last) > 2 else "",
            "机构投资者持有比例": holder_last[3] if len(holder_last) > 3 else "",
            "个人投资者持有份额": holder_last[4] if len(holder_last) > 4 else "",
            "个人投资者持有比例": holder_last[5] if len(holder_last) > 5 else "",
            "内部持有份额": "",
        }
    else:
        holder_value_map = {
            "机构投资者持有份额": "",
            "机构投资者持有比例": "",
            "个人投资者持有份额": "",
            "个人投资者持有比例": "",
            "内部持有份额": "",
        }

    table10 = _metrics_table_by_range(selected_metrics, 84, 88)
    table10_label_col = _find_metric_label_col(table10)
    table10_value_col = _find_metric_value_col(table10)
    table10[table10_value_col] = table10[table10_label_col].map(holder_value_map).fillna(table10[table10_value_col])
    table10 = _finalize_metric_table_values(table10)

    fundraising_map = {c: "" for c in ["募集起始日", "募集截止日", "募集份额总额", "有效认购户数"]}
    if not fundraising_table.empty and len(fundraising_table) >= 1:
        r = fundraising_table.fillna("").astype(str).iloc[0]
        for k in fundraising_map:
            if k in fundraising_table.columns:
                fundraising_map[k] = str(r[k]).strip()

    table11 = _metrics_table_by_range(selected_metrics, 89, 92)
    table11_label_col = _find_metric_label_col(table11)
    table11_value_col = _find_metric_value_col(table11)
    table11[table11_value_col] = table11[table11_label_col].map(fundraising_map).fillna(table11[table11_value_col])
    table11 = _finalize_metric_table_values(table11)

    table08 = _ensure_nonempty_domain_table(
        selected_top_holdings,
        ["持仓排名", "股票/债券代码", "股票/债券名称", "持仓数量", "公允价值", "占基金资产净值比例"],
    )
    table09 = _ensure_nonempty_domain_table(
        selected_industry,
        ["行业类别", "行业公允价值", "占净值比例"],
    )

    outputs: Dict[str, pd.DataFrame] = {
        "表01_基本信息": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 1, 9)),
            "基本信息项",
        ),
        "表02_主要财务指标": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 10, 17)),
            "财务指标项",
        ),
        "表03_净值表现": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 18, 25)),
            "净值表现项",
        ),
        "表04_资产负债表": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 26, 46)),
            "资产负债项目",
        ),
        "表05_利润表": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 47, 56)),
            "利润项目",
        ),
        "表06_净资产变动表": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 57, 61)),
            "净资产变动项目",
        ),
        "表07_投资组合报告": _rename_metric_label_column(
            _finalize_metric_table_values(_metrics_table_by_range(selected_metrics, 62, 74)),
            "投资组合项目",
        ),
        "表08_前十大持仓": table08,
        "表09_行业配置": table09,
        "表10_基金持有人结构": _rename_metric_label_column(table10, "持有人结构项"),
        "表11_新发与募集信息": _rename_metric_label_column(table11, "募集信息项"),
    }

    # Keep explicit table-level coverage in each metric table for quick QA.
    for key in [
        "表01_基本信息",
        "表02_主要财务指标",
        "表03_净值表现",
        "表04_资产负债表",
        "表05_利润表",
        "表06_净资产变动表",
        "表07_投资组合报告",
        "表10_基金持有人结构",
        "表11_新发与募集信息",
    ]:
        table = outputs[key]
        if "数值" in table.columns and len(table) > 0:
            hit_count = int((table["数值"].astype(str) != MISSING_TOKEN).sum())
            coverage = f"{(hit_count / len(table)) * 100:.1f}%"
            table["表覆盖率"] = coverage
            outputs[key] = table

    if include_raw_tables:
        for name, table in named_tables.items():
            outputs[name] = table

    return outputs
