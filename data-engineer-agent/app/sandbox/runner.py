import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    result_json: dict


class SandboxRunner:
    def run(self, script: str, timeout_seconds: int = 90) -> SandboxResult:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script_path = tmp_path / "script.py"
            output_dir = tmp_path / "output"
            output_dir.mkdir()
            script = script.replace("/work/output", str(output_dir))
            script_path.write_text(script)

            proc = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            result_path = output_dir / "result.json"
            result_json = {}
            if result_path.exists():
                result_json = json.loads(result_path.read_text())

            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                result_json=result_json,
            )
