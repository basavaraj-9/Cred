import json
from dataclasses import dataclass
from pathlib import Path

TAXONOMY_PATH = Path(__file__).parent / "taxonomy" / "domain_taxonomy_v1.json"


@dataclass(frozen=True)
class Taxonomy:
    version: str
    paths: tuple[tuple[str, str, str, str], ...]

    def path_for(self, sub_domain: str) -> tuple[str, str, str, str]:
        for path in self.paths:
            if path[3] == sub_domain:
                return path
        raise ValueError(f"Unknown sub-domain: {sub_domain}")

    def contains(self, path: tuple[str, str, str, str]) -> bool:
        return path in self.paths

    def counts(self) -> dict[str, int]:
        return {
            "sectors": len({path[0] for path in self.paths}),
            "industries": len({path[1] for path in self.paths}),
            "domains": len({path[2] for path in self.paths}),
            "sub_domains": len({path[3] for path in self.paths}),
        }


def load_taxonomy(path: Path = TAXONOMY_PATH) -> Taxonomy:
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("version")
    rows = data.get("paths")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Taxonomy version is required")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Taxonomy paths must be a nonempty list")
    paths: list[tuple[str, str, str, str]] = []
    parents: list[dict[str, str]] = [{}, {}, {}]
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != 4
            or not all(isinstance(x, str) and x.strip() for x in row)
        ):
            raise ValueError("Each taxonomy path requires four nonempty labels")
        item = tuple(row)
        if item in paths:
            raise ValueError("Duplicate taxonomy path")
        for level in range(1, 4):
            parent = parents[level - 1].setdefault(item[level], item[level - 1])
            if parent != item[level - 1]:
                raise ValueError(f"Taxonomy label has multiple parents: {item[level]}")
        paths.append(item)
    return Taxonomy(version, tuple(paths))
