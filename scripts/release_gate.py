"""Validate release identity without publishing or executing distribution contents."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
from pathlib import Path
import tarfile
import zipfile

try:
    import tomllib
except ImportError:  # Python 3.9/3.10 development extra
    import tomli as tomllib


def validate(project: Path, distributions: Path, tag: str | None = None) -> str:
    with project.open("rb") as stream:
        metadata = tomllib.load(stream)["project"]
    version = metadata["version"]
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"release tag must equal v{version}")
    wheels = list(distributions.glob("*.whl"))
    sdists = list(distributions.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("require exactly one wheel and sdist")
    with zipfile.ZipFile(wheels[0]) as wheel:
        records = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(records) != 1:
            raise ValueError("wheel metadata missing or ambiguous")
        wheel_metadata = BytesParser().parsebytes(wheel.read(records[0]))
        if "jukto/py.typed" not in wheel.namelist():
            raise ValueError("wheel missing jukto/py.typed")
    with tarfile.open(sdists[0], "r:gz") as sdist:
        records = [member for member in sdist.getmembers() if len(Path(member.name).parts) == 2 and member.name.endswith("/PKG-INFO")]
        if len(records) != 1 or not records[0].isfile():
            raise ValueError("sdist metadata missing or ambiguous")
        stream = sdist.extractfile(records[0])
        if stream is None:
            raise ValueError("sdist metadata unreadable")
        sdist_metadata = BytesParser().parsebytes(stream.read())
    for record in (wheel_metadata, sdist_metadata):
        if record["Name"] != metadata["name"] or record["Version"] != version:
            raise ValueError("distribution name/version differs from pyproject.toml")
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(f"Validated distributions for jukto {validate(args.project, args.dist, args.tag)}")
