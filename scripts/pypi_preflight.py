"""Fail-closed PyPI preflight for GitHub Actions publishing.

Checks if *this exact immutable version* already exists on the chosen index.
A 404 means the version is not yet published. Other HTTP/network errors
prevent publishing rather than guessing that the package is absent.

This check does not confer ownership of a PyPI name and is not a substitute
for the Trusted Publisher OIDC permissions or GitHub environment protection.
"""
import os
from pathlib import Path
import re
import tomllib
from urllib.error import HTTPError
from urllib.request import Request, urlopen


INDEX_URLS = {
    "pypi": "https://pypi.org/pypi",
    "testpypi": "https://test.pypi.org/pypi",
}
PROJECT_NAME = "nexo-agent-protocol"


def publication_target(event, ref, selected_index):
    """Determine permitted destination without trusting arbitrary inputs."""
    if ref != "refs/heads/main":
        raise ValueError("PyPI publishing requires the main branch")
    if event == "push":
        return "pypi"
    if event == "workflow_dispatch" and selected_index in INDEX_URLS:
        return selected_index
    raise ValueError("unsupported publication event or index")


def package_version(root):
    root = Path(root)
    import_name = root / "python/nexo/__init__.py"
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project["name"] != PROJECT_NAME:
        raise ValueError("unexpected distribution name")
    version = project["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?", version):
        raise ValueError("unsupported distribution version")
    if f'__version__ = "{version}"' not in import_name.read_text(encoding="utf-8"):
        raise ValueError("SDK and distribution versions differ")
    return version


def version_exists(index, version, *, opener=urlopen):
    """True only on a successful version-specific PyPI API response."""
    if index not in INDEX_URLS:
        raise ValueError("unknown package index")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?", version):
        raise ValueError("invalid package version")
    endpoint = f"{INDEX_URLS[index]}/{PROJECT_NAME}/{version}/json"
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "User-Agent": "nexo-release-preflight/1"},
    )
    try:
        with opener(request, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError("unexpected PyPI status; refusing to publish")
            # Accept only a well-formed version-specific response.
            import json
            info = json.load(response)["info"]
            if info.get("version") != version:
                raise RuntimeError("PyPI response version mismatch")
            if info.get("name", "").lower().replace("_", "-") != PROJECT_NAME:
                raise RuntimeError("PyPI response project name mismatch")
            return True
    except HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(f"PyPI API HTTP {exc.code}; refusing to publish") from exc


def main():
    event = os.environ["GITHUB_EVENT_NAME"]
    ref = os.environ["GITHUB_REF"]
    index = publication_target(event, ref, os.environ.get("PUBLISH_INDEX", ""))
    version = package_version(Path(__file__).resolve().parents[1])
    exists = version_exists(index, version)
    status = "already published; skipping duplicate upload" if exists else "unpublished; upload authorized by workflow"
    print(f"{PROJECT_NAME} {version} on {index}: {status}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"should_publish={'false' if exists else 'true'}\n")
        output.write(f"target={index}\n")


if __name__ == "__main__":
    main()
