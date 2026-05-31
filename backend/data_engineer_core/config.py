from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = Path(__file__).resolve().parent
    sources_path: Path = root_dir / "registry" / "sources.yaml"
    datasets_path: Path = root_dir / "registry" / "datasets.yaml"


settings = Settings()
