"""Download the open datasets into data/raw.

The download uses only the Python standard library, so it also works before the
full environment is installed. Each file is checked against the checksum that
the data publisher gives. A partly downloaded file resumes where it stopped.

PhysioNet can be very slow to download from. PhysioNet also publishes its open
datasets in a public mirror on Amazon S3, so the script tries the mirror first.
Every file must still match the checksum that PhysioNet publishes for the cited
version. If a mirrored file does not match, the script fetches it from PhysioNet.

The raw files are listed in .gitignore and must never be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rozmarra.config import RAW_DIR

USER_AGENT = "rozmarra-dataset-download/0.1 (research prototype)"
CHUNK_SIZE = 1024 * 1024
ATTEMPTS = 3

SHANGHAI_URL = "https://ndownloader.figshare.com/files/42966622"
SHANGHAI_MD5 = "4bfb61cfa506b48155fd9e841ee48e21"

PHYSIONET = "https://physionet.org/files"
PHYSIONET_MIRROR = "https://physionet-open.s3.amazonaws.com"

CGMACROS_BASE = f"{PHYSIONET}/cgmacros/1.0.0"
CGMACROS_MIRROR = f"{PHYSIONET_MIRROR}/cgmacros/1.0.0"
CGMACROS_ZIP = "CGMacros_dateshifted365.zip"

DATASETS = ("shanghai", "cgmacros")
DATASET_FOLDERS = {"shanghai": "shanghai_t2dm", "cgmacros": "cgmacros"}


@dataclass(frozen=True)
class RemoteFile:
    """One file to download, with its target path inside data/raw.

    The script tries the addresses in order and keeps the first file whose
    checksum matches.
    """

    urls: tuple[str, ...]
    target: Path
    checksum: str | None = None  # The form is "md5:<hex>" or "sha256:<hex>".
    extract: bool = False


def parse_checksums(text: str) -> dict[str, str]:
    """Turn the lines of a PhysioNet SHA256SUMS.txt file into a dictionary of path to hash."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            sums[parts[1].lstrip("*").strip()] = parts[0].lower()
    return sums


def _sha256(sums: dict[str, str], name: str) -> str | None:
    return f"sha256:{sums[name]}" if name in sums else None


def shanghai_files() -> list[RemoteFile]:
    return [
        RemoteFile(
            urls=(SHANGHAI_URL,),
            target=Path(DATASET_FOLDERS["shanghai"]) / "diabetes_datasets.zip",
            checksum=f"md5:{SHANGHAI_MD5}",
            extract=True,
        )
    ]


def cgmacros_files(sums: dict[str, str]) -> list[RemoteFile]:
    return [
        RemoteFile(
            urls=(f"{CGMACROS_MIRROR}/{name}", f"{CGMACROS_BASE}/{name}"),
            target=Path(DATASET_FOLDERS["cgmacros"]) / name,
            checksum=_sha256(sums, name),
            extract=name.endswith(".zip"),
        )
        for name in (CGMACROS_ZIP, "LICENSE.txt")
    ]


def _open(url: str, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(request, timeout=60)


def _fetch_text(url: str) -> str:
    with _open(url) as response:
        return response.read().decode("utf-8")


def _file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_matches(path: Path, checksum: str | None) -> bool:
    if not path.exists():
        return False
    if checksum is None:
        return path.stat().st_size > 0
    algorithm, expected = checksum.split(":", 1)
    return _file_hash(path, algorithm) == expected


def _download_once(url: str, target: Path) -> None:
    partial = target.with_name(target.name + ".part")
    done = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={done}-"} if done else {}
    try:
        response = _open(url, headers)
    except urllib.error.HTTPError as error:
        if error.code == 416:
            # The server cannot resume this partial file, so the next attempt starts again.
            partial.unlink(missing_ok=True)
        raise
    with response:
        resumed = response.status == 206
        if not resumed:
            done = 0
        length = response.headers.get("Content-Length")
        total = done + int(length) if length else None
        next_report = 0.1
        with partial.open("ab" if resumed else "wb") as handle:
            for chunk in iter(lambda: response.read(CHUNK_SIZE), b""):
                handle.write(chunk)
                done += len(chunk)
                if total and total > 20 * CHUNK_SIZE and done / total >= next_report:
                    print(f"    {done / total:.0%} of {total / CHUNK_SIZE:.1f} MB", flush=True)
                    next_report += 0.1
    partial.replace(target)


def _download_with_retries(url: str, target: Path) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            _download_once(url, target)
            return
        except urllib.error.HTTPError as error:
            if error.code == 404 or attempt == ATTEMPTS:
                raise
            print(f"    Attempt {attempt} failed ({error}). The script will try again.")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == ATTEMPTS:
                raise
            print(f"    Attempt {attempt} failed ({error}). The script will try again.")
        time.sleep(5 * attempt)


def _extract(archive: Path) -> None:
    """Extract a ZIP file next to itself, unless an earlier run already did so."""
    marker = archive.with_name(archive.name + ".extracted")
    if marker.exists():
        return
    destination = archive.parent.resolve()
    print(f"  Extracting {archive.name} ...", flush=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            # This check refuses any entry that would land outside the destination folder.
            if not (destination / member.filename).resolve().is_relative_to(destination):
                raise RuntimeError(
                    f"The archive entry '{member.filename}' points outside the folder."
                )
        bundle.extractall(destination)
    marker.write_text("The archive was extracted successfully.\n", encoding="utf-8")


def download(remote: RemoteFile, raw_dir: Path = RAW_DIR) -> Path:
    target = raw_dir / remote.target
    target.parent.mkdir(parents=True, exist_ok=True)
    name = remote.target.as_posix()
    if _checksum_matches(target, remote.checksum):
        print(f"  {name} is already present and its checksum matches.", flush=True)
    else:
        target.unlink(missing_ok=True)
        for url in remote.urls:
            print(f"  Downloading {name} from {url.split('/')[2]} ...", flush=True)
            try:
                _download_with_retries(url, target)
            except urllib.error.URLError as error:
                print(f"    The download from this address failed ({error}).", flush=True)
                # A partial file from one address must not be resumed from another address.
                target.with_name(target.name + ".part").unlink(missing_ok=True)
                continue
            if _checksum_matches(target, remote.checksum):
                break
            print("    The checksum does not match, so the script will try the next address.")
            target.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"No address gave a correct copy of {name}.")
    if remote.extract:
        _extract(target)
    return target


def files_for(dataset: str) -> list[RemoteFile]:
    if dataset == "shanghai":
        return shanghai_files()
    if dataset == "cgmacros":
        return cgmacros_files(parse_checksums(_fetch_text(f"{CGMACROS_BASE}/SHA256SUMS.txt")))
    raise ValueError(f"The dataset '{dataset}' is not known. Please choose one of {DATASETS}.")


def download_datasets(datasets: Iterable[str], raw_dir: Path = RAW_DIR) -> None:
    for dataset in datasets:
        print(f"Dataset: {dataset}", flush=True)
        for remote in files_for(dataset):
            download(remote, raw_dir)
        folder = raw_dir / DATASET_FOLDERS[dataset]
        print(f"The {dataset} dataset is ready in {folder}.", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the open datasets into data/raw.")
    parser.add_argument(
        "datasets", nargs="*", help=f"Any of {', '.join(DATASETS)}. The default is all."
    )
    args = parser.parse_args(argv)
    unknown = [name for name in args.datasets if name not in DATASETS]
    if unknown:
        parser.error(f"These datasets are not known: {', '.join(unknown)}.")
    download_datasets(args.datasets or DATASETS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
