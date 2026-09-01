from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def resolve_from_project_root(rel: str | Path) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    return project_root() / p