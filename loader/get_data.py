"""Fetch the pinned, schema-compatible public CSV snapshot without credentials.

Run inside the loader container, or locally:
  python3 loader/get_data.py --data-dir data --verify
Existing valid data is reused offline. Files are checked before atomic rename.
See docs/SOURCES.md for the upstream licence and metadata-table boundary.
"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import urllib.request

MANIFEST = pathlib.Path(__file__).with_name("sources.json")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def validate(path, entry, check_hash=False):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        header = next(csv.reader(stream), [])
    if header != entry["header"]:
        raise ValueError(f"{path}: unexpected column order. Refusing positional database COPY.")
    if check_hash:
        expected = {entry.get("output_sha256", entry["sha256"]), entry.get("legacy_local_sha256")}
        if digest(path) not in expected:
            raise ValueError(f"{path}: checksum differs from the pinned source snapshot.")


def ensure_dataset(data_dir="/data", verify=False):
    base = pathlib.Path(data_dir)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["files"]:
        destination = base / entry["path"]
        if destination.exists():
            validate(destination, entry, check_hash=verify)
            continue
        if os.getenv("DOWNLOAD_DATA", "1") == "0":
            raise FileNotFoundError(f"Missing {destination}; DOWNLOAD_DATA=0 prevents automatic retrieval.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".download.tmp")
        normalized = destination.with_suffix(".normalized.tmp")
        print(f"[get] downloading {entry['table']} ({entry['bytes']/1024**2:.1f} MiB)", flush=True)
        try:
            request = urllib.request.Request(entry["url"], headers={"User-Agent": "Calcio-Champagne-source-loader/2"})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
                while block := response.read(1024 * 1024):
                    stream.write(block)
            if digest(temporary) != entry["sha256"]:
                raise ValueError(f"Downloaded {entry['table']} checksum does not match the pinned revision.")
            if entry.get("normalize"):
                with temporary.open(newline="", encoding="utf-8") as source, normalized.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=entry["header"], lineterminator="\n")
                    writer.writeheader()
                    for row in csv.DictReader(source):
                        writer.writerow({key: row.get(key, "") for key in entry["header"]})
                validate(normalized, entry, check_hash=True)
                normalized.replace(destination)
            else:
                validate(temporary, entry, check_hash=True)
                temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
            normalized.unlink(missing_ok=True)
    print(f"[get] {len(manifest['files'])} source tables ready; revision {manifest['revision'][:12]}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/data")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    ensure_dataset(args.data_dir, verify=args.verify)
