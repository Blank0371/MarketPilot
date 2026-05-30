from app.config import settings
from app.registry.loader import RegistryLoader


def test_registry_loads() -> None:
    loader = RegistryLoader(settings.sources_path, settings.datasets_path)
    assert len(loader.load_sources()) >= 1
    assert len(loader.load_datasets()) >= 1
