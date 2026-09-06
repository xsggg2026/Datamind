from typing import Dict, List

FIELD_TAG_CANDIDATES: Dict[str, List[str]] = {
    "company": ["companyname", "managername", "fundcompany", "trustee"],
    "fund_name": ["fundname", "productname", "securityname", "scheme"],
    "fund_code": ["fundcode", "securitycode", "productcode", "maincode"],
    "report_period": ["reportperiod", "period", "asofdate", "reportdate"],
    "share_class": ["shareclass", "class", "fundsharetype"],
    "fund_type": ["fundtype", "category", "producttype"],
    "benchmark": ["benchmark", "performancebenchmark", "comparisonbenchmark"],
    "strategy": ["strategy", "investmentstrategy", "benchmarkstyle"],
    "fund_nav_total": ["fundnav", "totalnetasset", "netassetvalue", "assetnetvalue"],
    "fund_units_total": ["totalfundunits", "fundsharesoutstanding", "fundsharestotal"],
    "unit_nav": ["unitnav", "navperunit", "fundunitnav"],
    "unit_nav_growth_rate": ["unitnavgrowthrate", "returnrate", "growthrate", "periodreturn"],
    "benchmark_return_rate": ["benchmarkreturnrate", "benchmarkgrowthrate", "benchreturn"],
    "equity_ratio": ["equityratio", "stockratio", "equityallocation"],
    "bond_ratio": ["bondratio", "fixedincomeratio", "bondallocation"],
    "cash_ratio": ["cashratio", "cashallocation", "cashandcashratio"],
}

FIELD_CONCEPT_KEYWORDS: Dict[str, List[str]] = {
    "company": ["manager", "fundmanager", "company", "managementcompany", "基金管理人", "管理人"],
    "fund_name": ["fundname", "securityname", "productname", "基金名称", "基金简称"],
    "fund_code": ["fundcode", "securitycode", "code", "主代码", "基金代码"],
    "report_period": ["reportperiod", "periodend", "asofdate", "报告期", "截至日期"],
    "share_class": ["shareclass", "class", "份额类别", "基金份额类别"],
    "fund_type": ["fundtype", "category", "riskreturn", "基金类型", "风险收益特征"],
    "benchmark": ["benchmark", "performancebenchmark", "业绩比较基准"],
    "strategy": ["strategy", "investmentstrategy", "投资策略"],
    "fund_nav_total": ["netassetvalue", "totalnetasset", "fundnav", "期末基金资产净值", "基金资产净值", "0505"],
    "fund_units_total": ["fundunitstotal", "sharesoutstanding", "fundshares", "期末基金份额总额", "基金份额总额"],
    "unit_nav": ["unitnav", "navperunit", "份额净值", "期末基金份额净值", "0506"],
    "unit_nav_growth_rate": ["unitnavgrowthrate", "returnrate", "growthrate", "净值增长率", "份额净值增长率"],
    "benchmark_return_rate": ["benchmarkreturnrate", "benchmarkgrowthrate", "业绩比较基准收益率"],
    "equity_ratio": ["equityratio", "stockratio", "权益投资占比", "股票资产占比"],
    "bond_ratio": ["bondratio", "fixedincomeratio", "债券投资占比", "债券资产占比"],
    "cash_ratio": ["cashratio", "cashallocation", "现金占比", "银行存款和结算备付金"],
}

SHARE_CLASS_PATTERNS: Dict[str, List[str]] = {
    "A": ["a类", "aclass", "classa", "份额a", "am份额", "a share"],
    "C": ["c类", "cclass", "classc", "份额c", "c share"],
}

DEFAULT_TEXT_FIELDS = {
    "company",
    "fund_name",
    "fund_code",
    "report_period",
    "share_class",
    "fund_type",
    "benchmark",
    "strategy",
}
