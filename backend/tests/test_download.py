import zipfile

import pytest

from rozmarra.data import download as dl


def test_parse_checksums_reads_physionet_lines():
    text = "abc123  Demographics.csv\nDEF456 *001/HR_001.csv\n\n"
    assert dl.parse_checksums(text) == {"Demographics.csv": "abc123", "001/HR_001.csv": "def456"}


def test_bigideas_selection_has_four_files_for_each_participant():
    files = dl.bigideas_files({})
    csv_files = [f for f in files if f.target.parts[1].isdigit()]
    assert len(csv_files) == 16 * 4
    assert not any("ACC_" in url or "BVP_" in url for f in files for url in f.urls)


def test_physionet_files_try_the_mirror_first_and_physionet_second():
    for remote in dl.cgmacros_files({}) + dl.bigideas_files({}):
        assert remote.urls[0].startswith(dl.PHYSIONET_MIRROR)
        assert remote.urls[1].startswith(dl.PHYSIONET)


def test_a_file_with_the_wrong_checksum_is_not_accepted(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_bytes(b"glucose\n100\n")
    assert dl._checksum_matches(path, "sha256:" + "0" * 64) is False
    assert dl._checksum_matches(path, None) is True


def test_extract_refuses_entries_outside_the_folder(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.txt", "This file must not be written.")
    with pytest.raises(RuntimeError):
        dl._extract(archive)
    assert not (tmp_path.parent / "outside.txt").exists()
