from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = Path(__file__).resolve().parents[1]
    sources_path: Path = root_dir / "app" / "registry" / "sources.yaml"
    datasets_path: Path = root_dir / "app" / "registry" / "datasets.yaml"


settings = Settings()
