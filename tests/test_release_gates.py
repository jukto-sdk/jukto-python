"""Offline regressions for release provenance and distribution validation."""
import importlib.util
import io
from pathlib import Path
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def gate():
    spec = importlib.util.spec_from_file_location("release_gate", ROOT / "scripts/release_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifacts(tmp_path, version="0.1.0", typed=True):
    with zipfile.ZipFile(tmp_path / "jukto.whl", "w") as wheel:
        wheel.writestr("jukto-0.1.0.dist-info/METADATA", f"Name: jukto\nVersion: {version}\n")
        if typed:
            wheel.writestr("jukto/py.typed", "")
    with tarfile.open(tmp_path / "jukto.tar.gz", "w:gz") as archive:
        body = f"Name: jukto\nVersion: {version}\n".encode()
        info = tarfile.TarInfo("jukto-0.1.0/PKG-INFO")
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    return tmp_path


def test_validated_release_artifacts(tmp_path):
    gate().validate(ROOT / "pyproject.toml", artifacts(tmp_path), "v0.1.0")


@pytest.mark.parametrize("tag", ["v0.2.0", "main", "0.1.0", "v0.1.0;echo unsafe"])
def test_wrong_tag_is_rejected(tmp_path, tag):
    with pytest.raises(ValueError, match="tag"):
        gate().validate(ROOT / "pyproject.toml", artifacts(tmp_path), tag)


def test_stale_artifact_version_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="version"):
        gate().validate(ROOT / "pyproject.toml", artifacts(tmp_path, "0.0.9"), "v0.1.0")


def test_untyped_wheel_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="py.typed"):
        gate().validate(ROOT / "pyproject.toml", artifacts(tmp_path, typed=False), "v0.1.0")


def test_missing_distribution_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="wheel and sdist"):
        gate().validate(ROOT / "pyproject.toml", tmp_path, "v0.1.0")


def test_publication_requires_checks_and_build():
    # BaseLoader avoids YAML 1.1 treating the GitHub "on" key as a boolean.
    import yaml
    workflow = yaml.load((ROOT / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    publish = jobs["pypi-publish"]
    assert {"checks", "build"}.issubset(set(publish["needs"]))
    assert "if" not in publish  # Never override the default success dependency gate.
    assert publish["environment"]["name"] == "pypi"
    assert jobs["checks"]["uses"] == "./.github/workflows/checks.yml"
    assert jobs["checks"]["with"]["ref"] == "${{ needs.resolve.outputs.sha }}"
    checkout = next(step for step in jobs["build"]["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ needs.resolve.outputs.sha }}"
    assert not any("checkout" in step.get("uses", "") for step in publish["steps"])


def test_sdist_alone_has_wrong_version(tmp_path):
    artifacts(tmp_path)
    with tarfile.open(tmp_path / "jukto.tar.gz", "w:gz") as archive:
        body = b"Name: jukto\nVersion: 0.0.9\n"
        info = tarfile.TarInfo("jukto-0.1.0/PKG-INFO")
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    with pytest.raises(ValueError, match="version"):
        gate().validate(ROOT / "pyproject.toml", tmp_path, "v0.1.0")


def test_duplicate_wheels_are_rejected(tmp_path):
    artifacts(tmp_path)
    (tmp_path / "stale.whl").write_bytes((tmp_path / "jukto.whl").read_bytes())
    with pytest.raises(ValueError, match="wheel and sdist"):
        gate().validate(ROOT / "pyproject.toml", tmp_path, "v0.1.0")


def test_supported_versions_receive_all_checks():
    import yaml
    workflow = yaml.load((ROOT / ".github/workflows/checks.yml").read_text(), Loader=yaml.BaseLoader)
    job = workflow["jobs"]["check"]
    assert job["strategy"]["matrix"]["python-version"] == [f"3.{minor}" for minor in range(9, 16)]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    for command in ("python -m ruff", "python -m mypy", "python -m pytest", "python -m build", "python -m twine"):
        assert command in commands
    assert 'cd "$smoke_dir"' in commands
    assert '-I "$CHECKOUT/scripts/wheel_smoke.py"' in commands
    publish = yaml.load((ROOT / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader)
    steps = publish["jobs"]["build"]["steps"]
    download = next(step for step in steps if step.get("uses", "").startswith("actions/download-artifact@"))
    assert download["with"]["name"] == "distributions-python-3.14"
    assert not any("python -m build" in step.get("run", "") for step in steps)
