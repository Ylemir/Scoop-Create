"""Tests for manifest module: Manifest, build_manifest, merge, write."""

import json
from pathlib import Path

from scoop_create.manifest import (
    APP_TYPE_BOTH,
    APP_TYPE_CLI,
    APP_TYPE_GUI,
    Architecture,
    Manifest,
    ManifestInput,
    _build_autoupdate_url,
    _build_bin_field,
    build_manifest,
    load_existing_manifest,
    merge_manifest,
    prepare_manifest_data,
    write_manifest,
)


class TestArchitecture:
    """Tests for Architecture model."""

    def test_basic(self) -> None:
        arch = Architecture(url="https://example.com/app.zip", hash="abc123")
        assert arch.url == "https://example.com/app.zip"
        assert arch.hash == "abc123"


class TestManifest:
    """Tests for Manifest model."""

    def test_minimal(self) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        assert manifest.version == "1.0.0"
        assert manifest.license == "Unknown"
        assert manifest.bin is None
        assert manifest.shortcuts is None

    def test_to_dict(self) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        data = manifest.to_dict()
        assert data["version"] == "1.0.0"
        assert data["description"] == "Test"
        assert data["homepage"] == "https://example.com"

    def test_to_dict_excludes_none(self) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        data = manifest.to_dict()
        assert "bin" not in data
        assert "shortcuts" not in data

    def test_to_json(self) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        assert parsed["version"] == "1.0.0"


class TestBuildBinField:
    """Tests for _build_bin_field function."""

    def test_exe_different_name(self) -> None:
        result = _build_bin_field("app", "launcher.exe")
        assert result.bin == [["launcher.exe", "app"]]
        assert result.shortcuts == [["launcher.exe", "app"]]

    def test_non_exe(self) -> None:
        result = _build_bin_field("app", "app-1.0.zip")
        assert result.bin == "app.exe"
        assert result.shortcuts == [["app.exe", "app"]]

    def test_cli_exe_same_name(self) -> None:
        result = _build_bin_field("app", "app.exe", app_type=APP_TYPE_CLI)
        assert result.bin == "app.exe"
        assert result.shortcuts is None

    def test_cli_exe_different_name(self) -> None:
        result = _build_bin_field("app", "launcher.exe", app_type=APP_TYPE_CLI)
        assert result.bin == [["launcher.exe", "app"]]
        assert result.shortcuts is None

    def test_cli_zip(self) -> None:
        result = _build_bin_field("app", "app-1.0.zip", app_type=APP_TYPE_CLI)
        assert result.bin == "app.exe"
        assert result.shortcuts is None

    def test_gui_exe_different_name(self) -> None:
        result = _build_bin_field("app", "launcher.exe", app_type=APP_TYPE_GUI)
        assert result.bin is None
        assert result.shortcuts == [["launcher.exe", "app"]]

    def test_gui_zip(self) -> None:
        result = _build_bin_field("app", "app-1.0.zip", app_type=APP_TYPE_GUI)
        assert result.bin is None
        assert result.shortcuts == [["app.exe", "app"]]

    def test_both_exe_same_name(self) -> None:
        result = _build_bin_field("app", "app.exe", app_type=APP_TYPE_BOTH)
        assert result.bin == "app.exe"
        assert result.shortcuts == [["app.exe", "app"]]

    def test_both_exe_different_name_explicit(self) -> None:
        result = _build_bin_field("app", "launcher.exe", app_type=APP_TYPE_BOTH)
        assert result.bin == [["launcher.exe", "app"]]
        assert result.shortcuts == [["launcher.exe", "app"]]

    def test_both_non_exe_explicit(self) -> None:
        result = _build_bin_field("app", "app-1.0.zip", app_type=APP_TYPE_BOTH)
        assert result.bin == "app.exe"
        assert result.shortcuts == [["app.exe", "app"]]


class TestBuildAutoupdateUrl:
    """Tests for _build_autoupdate_url function."""

    def test_replace_version_in_filename(self) -> None:
        url = "https://github.com/owner/repo/releases/download/v1.0.0/app-1.0.0-x64.zip"
        result = _build_autoupdate_url(url, "1.0.0")
        assert (
            result
            == "https://github.com/owner/repo/releases/download/v$version/app-$version-x64.zip"
        )

    def test_replace_version_in_path(self) -> None:
        url = "https://example.com/1.0.0/download/1.0.0/app.zip"
        result = _build_autoupdate_url(url, "1.0.0")
        assert "$version" in result


class TestBuildManifest:
    """Tests for build_manifest function."""

    def test_basic(self) -> None:
        inp = ManifestInput(
            version="1.0.0",
            description="Test app",
            homepage="https://example.com",
            license_str="MIT",
            asset_url="https://example.com/app-1.0.0-x64.zip",
            asset_hash="abc123",
            asset_name="app-1.0.0-x64.zip",
            owner="owner",
            repo="repo",
            app_name="app",
        )
        manifest = build_manifest(inp)
        assert manifest.version == "1.0.0"
        assert manifest.description == "Test app"
        assert manifest.homepage == "https://example.com"
        assert manifest.license == "MIT"
        assert "64bit" in manifest.architecture
        assert (
            manifest.architecture["64bit"].url
            == "https://example.com/app-1.0.0-x64.zip"
        )
        assert manifest.architecture["64bit"].hash == "abc123"
        assert manifest.checkver == {"github": "https://github.com/owner/repo"}

    def test_empty_license_defaults_to_unknown(self) -> None:
        inp = ManifestInput(
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            license_str="",
            asset_url="https://example.com/app.zip",
            asset_hash="abc",
            asset_name="app.zip",
            owner="owner",
            repo="repo",
            app_name="app",
        )
        manifest = build_manifest(inp)
        assert manifest.license == "Unknown"


class TestMergeManifest:
    """Tests for merge_manifest function."""

    def test_simple_merge(self) -> None:
        existing = {"version": "0.9.0", "description": "Old"}
        new = {"version": "1.0.0", "homepage": "https://example.com"}
        result = merge_manifest(existing, new)
        assert result["version"] == "1.0.0"
        assert result["description"] == "Old"
        assert result["homepage"] == "https://example.com"

    def test_nested_merge(self) -> None:
        existing = {"architecture": {"64bit": {"url": "old.zip", "hash": "old"}}}
        new = {"architecture": {"64bit": {"url": "new.zip"}}}
        result = merge_manifest(existing, new)
        assert result["architecture"]["64bit"]["url"] == "new.zip"
        assert result["architecture"]["64bit"]["hash"] == "old"

    def test_ignore_fields_applied_before_merge(self, tmp_path: Path) -> None:
        manifest = Manifest(
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            license="MIT",
        )
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"version": "0.9.0", "license": "Apache-2.0"}))
        result = prepare_manifest_data(
            manifest,
            merge=True,
            output_path=path,
            ignore_fields=["license"],
        )
        assert result["license"] == "Apache-2.0"


class TestLoadExistingManifest:
    """Tests for load_existing_manifest function."""

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        result = load_existing_manifest(tmp_path / "nonexistent.json")
        assert result is None

    def test_valid_manifest(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"version": "1.0.0", "description": "Test"}))
        result = load_existing_manifest(path)
        assert result is not None
        assert result["version"] == "1.0.0"

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("not json")
        result = load_existing_manifest(path)
        assert result is None


class TestPrepareManifestData:
    """Tests for prepare_manifest_data function."""

    def test_no_merge(self) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        result = prepare_manifest_data(manifest, merge=False)
        assert result["version"] == "1.0.0"

    def test_merge_with_existing(self, tmp_path: Path) -> None:
        manifest = Manifest(
            version="2.0.0", description="New", homepage="https://example.com"
        )
        path = tmp_path / "manifest.json"
        path.write_text(
            json.dumps({"version": "1.0.0", "description": "Old", "extra": "kept"})
        )
        result = prepare_manifest_data(manifest, merge=True, output_path=path)
        assert result["version"] == "2.0.0"
        assert result["description"] == "New"
        assert result["extra"] == "kept"

    def test_merge_with_nonexistent_file(self, tmp_path: Path) -> None:
        manifest = Manifest(
            version="1.0.0", description="Test", homepage="https://example.com"
        )
        path = tmp_path / "nonexistent.json"
        result = prepare_manifest_data(manifest, merge=True, output_path=path)
        assert result["version"] == "1.0.0"

    def test_ignore_fields_no_effect_without_existing(self, tmp_path: Path) -> None:
        manifest = Manifest(
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            license="MIT",
        )
        path = tmp_path / "nonexistent.json"
        result = prepare_manifest_data(
            manifest, merge=True, output_path=path, ignore_fields=["license"]
        )
        assert "license" in result

    def test_ignore_fields_removes_nested(self, tmp_path: Path) -> None:
        manifest = Manifest(
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            architecture={"64bit": Architecture(url="new.zip", hash="new")},
        )
        path = tmp_path / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "version": "0.9.0",
                    "architecture": {"64bit": {"url": "old.zip", "hash": "old"}},
                }
            )
        )
        result = prepare_manifest_data(
            manifest,
            merge=True,
            output_path=path,
            ignore_fields=["architecture.64bit.hash"],
        )
        assert result["architecture"]["64bit"]["url"] == "new.zip"
        assert result["architecture"]["64bit"]["hash"] == "old"


class TestWriteManifest:
    """Tests for write_manifest function."""

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        manifest = {"version": "1.0.0"}
        path = tmp_path / "subdir" / "manifest.json"
        write_manifest(manifest, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == "1.0.0"

    def test_write_trailing_newline(self, tmp_path: Path) -> None:
        manifest = {"version": "1.0.0"}
        path = tmp_path / "manifest.json"
        write_manifest(manifest, path)
        content = path.read_text()
        assert content.endswith("\n")
