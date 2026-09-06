from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import re
from typing import Dict, List

from .config import FIELD_CONCEPT_KEYWORDS, FIELD_TAG_CANDIDATES, SHARE_CLASS_PATTERNS
from .models import FundRecord
from .pdf_parser import parse_pdf_file


def _local_name(tag: str) -> str:
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]", "", tag).lower()


@dataclass
class ContextInfo:
    context_id: str
    period: str
    dimensions_text: str


@dataclass
class Fact:
    concept: str
    value: str
    context_id: str
    period: str
    dimensions_text: str


def _build_index(root: ET.Element) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for elem in root.iter():
        key = _local_name(elem.tag)
        text = (elem.text or "").strip()
        if text and key not in index:
            index[key] = text
    return index


def _extract_contexts(root: ET.Element) -> Dict[str, ContextInfo]:
    contexts: Dict[str, ContextInfo] = {}
    for elem in root.iter():
        if _local_name(elem.tag) != "context":
            continue
        context_id = elem.attrib.get("id", "")
        if not context_id:
            continue

        period_value = ""
        dimensions: List[str] = []

        for child in elem.iter():
            local = _local_name(child.tag)
            text = (child.text or "").strip()
            if local in {"instant", "enddate", "startdate"} and text:
                period_value = text
            if local in {"explicitmember", "typedmember"}:
                dim = child.attrib.get("dimension", "")
                if dim:
                    dimensions.append(f"{dim}:{text}")
                elif text:
                    dimensions.append(text)

        context_blob = " ".join([context_id] + dimensions).lower()
        contexts[context_id] = ContextInfo(
            context_id=context_id,
            period=period_value,
            dimensions_text=context_blob,
        )
    return contexts


def _extract_facts(root: ET.Element, contexts: Dict[str, ContextInfo]) -> List[Fact]:
    facts: List[Fact] = []
    for elem in root.iter():
        if list(elem):
            continue
        text = (elem.text or "").strip()
        if not text:
            continue

        concept = _local_name(elem.tag)
        context_id = elem.attrib.get("contextRef", "") or elem.attrib.get("contextref", "")
        context = contexts.get(context_id)

        facts.append(
            Fact(
                concept=concept,
                value=text,
                context_id=context_id,
                period=context.period if context else "",
                dimensions_text=context.dimensions_text if context else "",
            )
        )
    return facts


def _detect_share_class(text: str) -> str:
    normalized = text.lower().replace(" ", "")
    for share, patterns in SHARE_CLASS_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                return share
    return "ALL"


def _match_score(field: str, concept: str) -> int:
    score = 0
    for keyword in FIELD_CONCEPT_KEYWORDS.get(field, []):
        normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]", "", keyword).lower()
        if not normalized:
            continue
        if concept == normalized:
            score = max(score, 10)
        elif normalized in concept:
            score = max(score, 6)
    return score


def _pick_fact_value(
    field: str,
    facts: List[Fact],
    share_class: str,
    fallback_index: Dict[str, str],
) -> str:
    best_value = ""
    best_score = -1

    for fact in facts:
        score = _match_score(field, fact.concept)
        if score <= 0:
            continue

        fact_share = _detect_share_class(fact.dimensions_text)
        if share_class != "ALL":
            if fact_share == share_class:
                score += 4
            elif fact_share != "ALL":
                score -= 3
        else:
            if fact_share == "ALL":
                score += 1

        if fact.period:
            score += 1

        if score > best_score:
            best_score = score
            best_value = fact.value

    if best_value:
        return best_value

    if share_class != "ALL":
        return ""

    candidates = FIELD_TAG_CANDIDATES.get(field, [])
    for candidate in candidates:
        if candidate in fallback_index:
            return fallback_index[candidate]
    return ""


def _pick_value(index: Dict[str, str], candidates: List[str]) -> str:
    for candidate in candidates:
        if candidate in index:
            return index[candidate]
    return ""


def parse_xbrl_file(file_path: Path) -> List[FundRecord]:
    tree = ET.parse(file_path)
    root = tree.getroot()
    index = _build_index(root)
    contexts = _extract_contexts(root)
    facts = _extract_facts(root, contexts)

    share_classes = {"ALL"}
    for context in contexts.values():
        share_classes.add(_detect_share_class(context.dimensions_text))
    share_classes = {s for s in share_classes if s}

    records: List[FundRecord] = []
    for share_class in sorted(share_classes):
        extracted = {
            "company": _pick_fact_value("company", facts, share_class, index),
            "fund_name": _pick_fact_value("fund_name", facts, share_class, index),
            "fund_code": _pick_fact_value("fund_code", facts, share_class, index),
            "report_period": _pick_fact_value("report_period", facts, share_class, index),
            "fund_type": _pick_fact_value("fund_type", facts, share_class, index),
            "benchmark": _pick_fact_value("benchmark", facts, share_class, index),
            "strategy": _pick_fact_value("strategy", facts, share_class, index),
            "fund_nav_total": _pick_fact_value("fund_nav_total", facts, share_class, index),
            "fund_units_total": _pick_fact_value("fund_units_total", facts, share_class, index),
            "unit_nav": _pick_fact_value("unit_nav", facts, share_class, index),
            "unit_nav_growth_rate": _pick_fact_value("unit_nav_growth_rate", facts, share_class, index),
            "benchmark_return_rate": _pick_fact_value("benchmark_return_rate", facts, share_class, index),
            "equity_ratio": _pick_fact_value("equity_ratio", facts, share_class, index),
            "bond_ratio": _pick_fact_value("bond_ratio", facts, share_class, index),
            "cash_ratio": _pick_fact_value("cash_ratio", facts, share_class, index),
        }

        company = extracted["company"] or _pick_value(index, FIELD_TAG_CANDIDATES["company"])
        fund_name = extracted["fund_name"] or file_path.stem

        meaningful = any(
            str(extracted[field]).strip()
            for field in [
                "fund_code",
                "report_period",
                "fund_nav_total",
                "unit_nav",
                "unit_nav_growth_rate",
                "equity_ratio",
                "bond_ratio",
                "cash_ratio",
            ]
        )
        if not meaningful:
            continue

        record = FundRecord(
            company=company or "unknown_company",
            fund_name=fund_name,
            fund_code=extracted["fund_code"],
            report_period=extracted["report_period"],
            share_class=share_class,
            fund_type=extracted["fund_type"],
            benchmark=extracted["benchmark"],
            strategy=extracted["strategy"],
            fund_nav_total=extracted["fund_nav_total"] or "0",
            fund_units_total=extracted["fund_units_total"] or "0",
            unit_nav=extracted["unit_nav"] or "0",
            unit_nav_growth_rate=extracted["unit_nav_growth_rate"] or "0",
            benchmark_return_rate=extracted["benchmark_return_rate"] or "0",
            equity_ratio=extracted["equity_ratio"] or "0",
            bond_ratio=extracted["bond_ratio"] or "0",
            cash_ratio=extracted["cash_ratio"] or "0",
            source_file=file_path.name,
        )
        records.append(record)

    if records:
        return records

    values = {field: _pick_value(index, candidates) for field, candidates in FIELD_TAG_CANDIDATES.items()}
    return [
        FundRecord(
            company=values.get("company", "") or "unknown_company",
            fund_name=values.get("fund_name", "") or file_path.stem,
            fund_code=values.get("fund_code", ""),
            report_period=values.get("report_period", ""),
            share_class=values.get("share_class", "") or "ALL",
            fund_type=values.get("fund_type", ""),
            benchmark=values.get("benchmark", ""),
            strategy=values.get("strategy", ""),
            fund_nav_total=values.get("fund_nav_total", "0"),
            fund_units_total=values.get("fund_units_total", "0"),
            unit_nav=values.get("unit_nav", "0"),
            unit_nav_growth_rate=values.get("unit_nav_growth_rate", "0"),
            benchmark_return_rate=values.get("benchmark_return_rate", "0"),
            equity_ratio=values.get("equity_ratio", "0"),
            bond_ratio=values.get("bond_ratio", "0"),
            cash_ratio=values.get("cash_ratio", "0"),
            source_file=file_path.name,
        )
    ]


def parse_folder(input_dir: Path) -> List[FundRecord]:
    if input_dir.is_file():
        files = [input_dir]
    else:
        files = sorted(
            list(input_dir.glob("*.xbrl"))
            + list(input_dir.glob("*.xml"))
            + list(input_dir.glob("*.pdf"))
        )
    records: List[FundRecord] = []
    for file in files:
        try:
            if file.suffix.lower() == ".pdf":
                records.extend(parse_pdf_file(file))
            else:
                records.extend(parse_xbrl_file(file))
        except Exception:
            # Skip malformed files and continue batch processing.
            continue
    return records
