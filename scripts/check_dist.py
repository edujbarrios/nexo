"""Validate a built PyPI release artifact before it may be uploaded.

Usage: python scripts/check_dist.py
Requires Python 3.11+ for tomllib; CI uses Python 3.12 for distribution checks.
"""
import email
import pathlib
import tarfile
import tomllib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
name = meta["project"]["name"]
version = meta["project"]["version"]
dist_stem = name.replace("-", "_")

wheels = list(DIST.glob("*.whl"))
sdists = list(DIST.glob("*.tar.gz"))
if len(wheels) != 1 or len(sdists) != 1:
    raise SystemExit("expected exactly one wheel and one source distribution")
wheel = wheels[0]
sdist = sdists[0]
if wheel.name != f"{dist_stem}-{version}-py3-none-any.whl":
    raise SystemExit("wheel is not the expected pure-Python universal artifact")
if sdist.name != f"{dist_stem}-{version}.tar.gz":
    raise SystemExit("source distribution name/version mismatch")

with zipfile.ZipFile(wheel) as archive:
    files = archive.namelist()
    for suffix in ("nexo/__init__.py", "nexo/__main__.py",
                   "nexo/nexo64.py", "nexo/transport.py"):
        if suffix not in files:
            raise SystemExit(f"missing required wheel source: {suffix}")
    metadata_files = [p for p in files if p.endswith(".dist-info/METADATA")]
    if len(metadata_files) != 1:
        raise SystemExit("wheel metadata missing or ambiguous")
    data = email.message_from_bytes(archive.read(metadata_files[0]))
    if data["Name"] != name or data["Version"] != version:
        raise SystemExit("wheel identity does not match pyproject.toml")
    if data.get("License-Expression") != "LicenseRef-NEXO-NC-ND-1.0":
        raise SystemExit("license expression missing from wheel metadata")
    if not any(p.endswith("/LICENSE") for p in files):
        raise SystemExit("wheel missing custom license text")

prefix = f"{dist_stem}-{version}/"
with tarfile.open(sdist) as archive:
    files = archive.getnames()
    for filename in ("pyproject.toml", "README.md", "LICENSE",
                     "python/nexo/__init__.py", "python/nexo/nexo64.py",
                     "python/nexo/transport.py"):
        if prefix + filename not in files:
            raise SystemExit(f"source distribution missing {filename}")

print(f"Validated PyPI artifacts: {wheel.name} and {sdist.name}")
