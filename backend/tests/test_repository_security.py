import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SECRET_PATTERNS = {
    "generic sk key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Dify app key": re.compile(r"\bapp-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Google-style API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT, text=True
    )
    return [ROOT / item for item in output.split("\0") if item]


def test_no_environment_files_are_tracked():
    forbidden = [
        path.relative_to(ROOT).as_posix()
        for path in tracked_files()
        if path.name == ".env" or path.name.startswith(".env.")
    ]
    assert forbidden == []


def test_no_high_confidence_secrets_are_tracked():
    findings: list[str] = []
    for path in tracked_files():
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {name}")
    assert findings == []

