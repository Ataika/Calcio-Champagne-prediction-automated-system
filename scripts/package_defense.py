#!/usr/bin/env python3
"""Create shareable archives without credentials, raw data or model artifacts."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / "defense/site/downloads"
PREFIX = "Calcio-Champagne-prediction-automated-system"
FORBIDDEN = {".env", ".env.local", ".env.production", "credentials.json"}
OMIT_PARTS = {".git", "node_modules", "__pycache__", "models", "data", "artifacts"}
OMIT_SUFFIXES = {".joblib", ".pyc", ".log"}
OMIT_ZIPS = {"Defense-Materials.zip", "Project-Package.zip"}


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE,
    ).stdout
    paths = [ROOT / value.decode("utf-8") for value in result.split(b"\0") if value]
    return [path for path in paths if path.is_file()]


def safe(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    # Finder and editor droppings: never useful to a reader, and .DS_Store
    # leaks local folder metadata.
    if rel.name == ".DS_Store" or rel.name.startswith("._"):
        return False
    if any(part in OMIT_PARTS for part in rel.parts):
        return False
    if rel.name in FORBIDDEN or rel.name in OMIT_ZIPS:
        return False
    if path.suffix.lower() in OMIT_SUFFIXES:
        return False
    # Include only reviewed screenshots copied into the defense website.
    if "artifacts" in rel.parts:
        return False
    return True


def write_zip(output: Path, files: list[tuple[Path, str]]) -> int:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for source, arcname in sorted(files, key=lambda item: item[1]):
            archive.write(source, arcname)
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt archive member: {bad}")
        names = archive.namelist()
        if any(Path(name).name in FORBIDDEN for name in names):
            raise RuntimeError("Credentials/configuration file entered the archive")
        return len(names)


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    all_files = [p for p in tracked_paths() if safe(p)]
    project = DOWNLOADS / "Project-Package.zip"
    project_members = [(p, f"{PREFIX}/{p.relative_to(ROOT).as_posix()}") for p in all_files]
    project_count = write_zip(project, project_members)

    included = []
    for relative in ("defense/START_HERE.md", "defense/curriculum.json"):
        p = ROOT / relative
        included.append((p, f"Calcio-Champagne-Defense/{Path(relative).name}"))
    for base, arcroot in ((ROOT / "defense/site", "Calcio-Champagne-Defense/site"),
                          (ROOT / "defense/materials", "Calcio-Champagne-Defense/materials")):
        for p in base.rglob("*"):
            # safe() here too: this walk does not go through tracked_paths()
            if p.is_file() and p.name not in OMIT_ZIPS and safe(p):
                included.append((p, f"{arcroot}/{p.relative_to(base).as_posix()}"))
    defense = DOWNLOADS / "Defense-Materials.zip"
    defense_count = write_zip(defense, included)
    print(f"{project.name}: {project.stat().st_size / 1024 / 1024:.2f} MiB · {project_count} files")
    print(f"{defense.name}: {defense.stat().st_size / 1024 / 1024:.2f} MiB · {defense_count} files")
    print("Excluded .env/secrets, raw data, model weights, Docker images and recursive archives.")


if __name__ == "__main__":
    main()
