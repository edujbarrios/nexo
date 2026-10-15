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
assert workflow["on"]["push"]["tags"] == ["v*"]
assert "workflow_dispatch" in workflow["on"]
assert workflow["permissions"] == {"contents": "read"}

jobs = workflow["jobs"]
assert {"build", "publish-pypi", "publish-testpypi"} == set(jobs)
assert jobs["build"]["permissions"] == {"contents": "read"}
assert jobs["publish-pypi"]["environment"]["name"] == "pypi"
assert jobs["publish-testpypi"]["environment"]["name"] == "testpypi"
assert jobs["publish-pypi"]["permissions"] == {"id-token": "write"}
assert jobs["publish-testpypi"]["permissions"] == {"id-token": "write"}
assert "push" in jobs["publish-pypi"]["if"]
assert "workflow_dispatch" in jobs["publish-testpypi"]["if"]
assert jobs["publish-pypi"]["needs"] == ["build"]
assert jobs["publish-testpypi"]["needs"] == ["build"]
for job in ("publish-pypi", "publish-testpypi"):
    actions = [step.get("uses", "") for step in jobs[job]["steps"]]
    assert "pypa/gh-action-pypi-publish@release/v1" in actions
    assert not any("checkout" in action for action in actions)
assert all(
    "password" not in str(step).lower() and "api_token" not in str(step).lower()
    for job in jobs.values() for step in job["steps"]
)
print("Release workflow OIDC and trigger policy validated")
