from pathlib import Path

import yaml

from backend.data_engineer_core.schemas.source_schema import DatasetDefinition, SourceDefinition


class RegistryLoader:
    def __init__(self, sources_path: Path, datasets_path: Path) -> None:
        self.sources_path = sources_path
        self.datasets_path = datasets_path

    def load_sources(self) -> list[SourceDefinition]:
        payload = yaml.safe_load(self.sources_path.read_text())
        return [SourceDefinition.model_validate(item) for item in payload]

    def load_datasets(self) -> list[DatasetDefinition]:
        payload = yaml.safe_load(self.datasets_path.read_text())
        return [DatasetDefinition.model_validate(item) for item in payload]

    def get_source(self, source_id: str) -> SourceDefinition:
        for source in self.load_sources():
            if source.id == source_id:
                return source
        raise KeyError(f"Unknown source_id: {source_id}")

    def find_datasets(self, domain: str, metric: str) -> list[DatasetDefinition]:
        return [
            dataset
            for dataset in self.load_datasets()
            if dataset.domain == domain and metric in dataset.metrics and dataset.verified
        ]
