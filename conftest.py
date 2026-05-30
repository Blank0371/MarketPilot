import sys
from pathlib import Path

# Ensure the repo root is importable so tests can `import backend.data_engineer`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
