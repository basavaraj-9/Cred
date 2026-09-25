import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.ml.domain.taxonomy import Taxonomy
from app.ml.domain.text_builder import build_text, text_hash

DATASET_VERSION = "domain_dataset_v1"
DATASET_PATH = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "ml"
    / "domain"
    / "versions"
    / "domain_dataset_v1.jsonl"
)


class DomainExample(BaseModel):
    example_id: str = Field(min_length=1)
    company_key: str = Field(min_length=1)
    document_key: str = Field(min_length=1)
    business_description: str = Field(min_length=1)
    products: list[str]
    services: list[str]
    operating_segments: list[str]
    sector: str
    industry: str
    domain: str
    sub_domain: str
    source: Literal["VERIFIED_REAL", "MANUALLY_CURATED", "SYNTHETIC", "PROXY"]
    label_quality: Literal["VERIFIED_REAL", "MANUALLY_CURATED", "SYNTHETIC", "PROXY"]
    dataset_version: str

    def input_text(self) -> str:
        return build_text(
            {
                "business_description": [self.business_description],
                "product": self.products,
                "service": self.services,
                "operating_segment": self.operating_segments,
            }
        )


def load_dataset(path: Path, taxonomy: Taxonomy) -> tuple[list[DomainExample], str]:
    content = path.read_bytes()
    rows = [
        DomainExample.model_validate(json.loads(line))
        for line in content.decode("utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("Training dataset is empty")
    seen_ids: set[str] = set()
    company_labels: dict[str, str] = {}
    document_owners: dict[str, str] = {}
    for row in rows:
        if row.dataset_version != DATASET_VERSION:
            raise ValueError("Dataset version mismatch")
        if row.example_id in seen_ids:
            raise ValueError("Duplicate example ID")
        seen_ids.add(row.example_id)
        if not taxonomy.contains((row.sector, row.industry, row.domain, row.sub_domain)):
            raise ValueError("Dataset label is outside taxonomy")
        old = company_labels.setdefault(row.company_key, row.sub_domain)
        if old != row.sub_domain:
            raise ValueError("One company has conflicting training labels")
        owner = document_owners.setdefault(row.document_key, row.company_key)
        if owner != row.company_key:
            raise ValueError("One document belongs to multiple companies")
        if not row.input_text():
            raise ValueError("Example has no business input")
    return rows, hashlib.sha256(content).hexdigest()


def split_by_company(rows: list[DomainExample], seed: int = 42) -> dict[str, list[DomainExample]]:
    by_label: dict[str, dict[str, list[DomainExample]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_label[row.sub_domain][row.company_key].append(row)
    rng = random.Random(seed)
    result: dict[str, list[DomainExample]] = {"train": [], "validation": [], "test": []}
    for companies in by_label.values():
        keys = sorted(companies)
        if len(keys) < 3:
            raise ValueError("Each trained class needs at least three distinct companies")
        rng.shuffle(keys)
        for index, key in enumerate(keys):
            split = "test" if index == 0 else "validation" if index == 1 else "train"
            result[split].extend(companies[key])
    assert_no_leakage(result)
    return result


def assert_no_leakage(splits: dict[str, list[DomainExample]]) -> None:
    seen_companies: set[str] = set()
    seen_examples: set[str] = set()
    seen_documents: set[str] = set()
    seen_inputs: set[str] = set()
    for name in ("train", "validation", "test"):
        rows = splits[name]
        companies = {row.company_key for row in rows}
        examples = {row.example_id for row in rows}
        documents = {row.document_key for row in rows}
        inputs = {text_hash(row.input_text()) for row in rows}
        if (
            seen_companies & companies
            or seen_examples & examples
            or seen_documents & documents
            or seen_inputs & inputs
        ):
            raise ValueError("Company, document, example, or exact input leakage across splits")
        seen_companies |= companies
        seen_examples |= examples
        seen_documents |= documents
        seen_inputs |= inputs


def dataset_report(
    rows: list[DomainExample], splits: dict[str, list[DomainExample]]
) -> dict[str, object]:
    return {
        "records": len(rows),
        "companies": len({row.company_key for row in rows}),
        "sources": dict(Counter(row.source for row in rows)),
        "split": {name: len(group) for name, group in splits.items()},
        "class_distribution": dict(Counter(row.sub_domain for row in rows)),
        "warnings": [
            label for label, count in Counter(row.sub_domain for row in rows).items() if count < 5
        ],
    }
