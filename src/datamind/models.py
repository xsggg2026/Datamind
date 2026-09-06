from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class FundRecord:
    company: str
    fund_name: str
    fund_code: str
    report_period: str
    share_class: str
    fund_type: str
    benchmark: str
    strategy: str
    fund_nav_total: float
    fund_units_total: float
    unit_nav: float
    unit_nav_growth_rate: float
    benchmark_return_rate: float
    equity_ratio: float
    bond_ratio: float
    cash_ratio: float
    source_file: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
