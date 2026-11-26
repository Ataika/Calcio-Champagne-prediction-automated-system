"""Exercise real public acquisition without touching the prepared source files.

Run inside the loader's pinned environment, with the project mounted at /source:
docker compose run --rm --no-deps -v "$PWD:/source:ro" -w /source loader \
  python scripts/check_download.py
Only the ~0.5 MiB team_children file is downloaded; other inputs are symlinked
read-only into a temporary directory. SHA/header checks run on the real result.
"""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from loader.get_data import ensure_dataset


def main():
    source = pathlib.Path("/data")
    with tempfile.TemporaryDirectory(prefix="calcio-download-") as temporary:
        target = pathlib.Path(temporary)
        for directory in source.iterdir():
            filename = directory / (directory.name + ".csv")
            if not filename.exists() or directory.name == "team_children":
                continue
            destination = target / directory.name / filename.name
            destination.parent.mkdir()
            destination.symlink_to(filename)
        ensure_dataset(target, verify=True)
        downloaded = target / "team_children/team_children.csv"
        assert downloaded.is_file() and not downloaded.is_symlink()
        assert downloaded.stat().st_size > 500_000
        print("Public no-login download, checksum validation and atomic placement passed")


if __name__ == "__main__":
    main()
