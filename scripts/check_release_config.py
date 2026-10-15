"""Static guards for the PyPI OIDC release workflow; called from CI.

PyYAML is a CI-only checker, never a runtime dependency of NEXO.
Use BaseLoader to avoid YAML 1.1 interpreting the GitHub 'on' key as True.
"""
from pathlib import Path
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]
workflow = yaml.load(
    (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"),
    Loader=yaml.BaseLoader,
)
project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
assert project["project"]["name"] == "nexo-agent-protocol"
assert set(workflow["on"]) == {"workflow_dispatch", "push"}
assert workflow["on"]["push"]["branches"] == ["main"]
assert "pyproject.toml" in workflow["on"]["push"]["paths"]
assert "python/**" in workflow["on"]["push"]["paths"]
assert ".github/workflows/release.yml" in workflow["on"]["push"]["paths"]
choice = workflow["on"]["workflow_dispatch"]["inputs"]["index"]
assert choice["type"] == "choice"
assert choice["required"] == "true"
assert choice["default"] == "testpypi"
assert choice["options"] == ["testpypi", "pypi"]
assert workflow["permissions"] == {"contents": "read"}

jobs = workflow["jobs"]
assert {"build", "publish-pypi", "publish-testpypi"} == set(jobs)
assert jobs["build"]["permissions"] == {"contents": "read"}
assert "refs/heads/main" in jobs["build"]["if"]
assert jobs["build"]["outputs"]["should_publish"] == "${{ steps.preflight.outputs.should_publish }}"
preflight = next(s for s in jobs["build"]["steps"] if s.get("id") == "preflight")
assert preflight["run"] == "python scripts/pypi_preflight.py"
assert "github.event_name == 'push'" in preflight["env"]["PUBLISH_INDEX"]
for s in jobs["build"]["steps"]:
    if s.get("name") in {
        "Install build and test tools", "Test source SDK",
        "Build source distribution and wheel",
        "Check metadata, wheel contents, license and README",
        "Smoke test the built wheel in a clean environment",
        "Confirm sdist can build a wheel", "Store validated artifacts",
    }:
        assert "steps.preflight.outputs.should_publish == 'true'" in s.get("if", "")
assert jobs["publish-pypi"]["environment"]["name"] == "pypi"
assert jobs["publish-testpypi"]["environment"]["name"] == "testpypi"
assert jobs["publish-pypi"]["permissions"] == {"id-token": "write"}
assert jobs["publish-testpypi"]["permissions"] == {"id-token": "write"}
assert "github.event_name == 'push'" in jobs["publish-pypi"]["if"]
assert "inputs.index == 'pypi'" in jobs["publish-pypi"]["if"]
assert "needs.build.outputs.should_publish == 'true'" in jobs["publish-pypi"]["if"]
assert "github.event_name == 'workflow_dispatch'" in jobs["publish-testpypi"]["if"]
assert "inputs.index == 'testpypi'" in jobs["publish-testpypi"]["if"]
assert "needs.build.outputs.should_publish == 'true'" in jobs["publish-testpypi"]["if"]
assert "refs/heads/main" in jobs["publish-pypi"]["if"]
assert "refs/heads/main" in jobs["publish-testpypi"]["if"]
assert jobs["publish-pypi"]["needs"] == ["build"]
assert jobs["publish-testpypi"]["needs"] == ["build"]
for job in ("publish-pypi", "publish-testpypi"):
    actions = [step.get("uses", "") for step in jobs[job]["steps"]]
    assert len(actions) == 2  # strictly download then OIDC publish
    assert "pypa/gh-action-pypi-publish@release/v1" in actions
    assert not any("checkout" in action for action in actions)
assert all(
    "password" not in str(step).lower() and "api_token" not in str(step).lower()
    for job in jobs.values() for step in job["steps"]
)
print("Automatic main-branch PyPI and manual TestPyPI OIDC policy validated")
