"""Run a test suite against each mutant of inventory.py. Prints JSON {killed: [...], survived: [...]}."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mutants import MUTANTS  # noqa: E402


def check(workspace, python):
    src = (Path(__file__).parent / "reference_inventory.py").read_text()
    killed, survived = [], []
    for name, old, new in MUTANTS:
        assert src.count(old) == 1, name
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            shutil.copytree(workspace, ws, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
            (ws / "src" / "inventory.py").write_text(src.replace(old, new))
            r = subprocess.run([python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"],
                               cwd=ws, capture_output=True, text=True, timeout=600)
            (killed if r.returncode != 0 else survived).append(name)
    return {"killed": killed, "survived": survived}


if __name__ == "__main__":
    print(json.dumps(check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.executable)))
