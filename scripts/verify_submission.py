from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "docs/QUEUE_DESIGN_DOCUMENT.md", "docs/SAFETY_EVALUATION_REPORT.md", "docs/ARCHITECTURE.md",
    "docs/AI_DEVELOPMENT_PROMPTS.md", "README.md", "docker-compose.yml",
]
for relative in REQUIRED:
    path = ROOT / relative
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Missing or empty deliverable: {relative}")
print(f"Verified {len(REQUIRED)} submission artifacts")
