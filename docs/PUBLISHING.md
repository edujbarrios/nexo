# Publishing NEXO to PyPI

This project is **source-available** under the custom
[NEXO Attribution–NonCommercial–NoDerivatives license](../LICENSE). Publishing
a wheel does not convert it to an open-source license or permit commercial use.

## Package identities and release scope

- **PyPI distribution:** `nexo-agent-protocol` (proposed; availability must
  be confirmed at the first registration).
- **Python import and CLI:** `nexo` (unchanged).
- **Version:** `0.1.0`, kept in `pyproject.toml` and `python/nexo/__init__.py`.
- **Original PyPI name `nexo`:** already used by an unrelated project; do
  **not** publish to it or instruct users to `pip install nexo`.
- **Optional native extension:** `nexo-native` is independent and is *not*
  published by this initial workflow. Avoid advertising the native extension
  as a PyPI dependency until supported wheels and ownership are established.

## 1. Validate local distribution artifacts

From the repository root, on Python 3.9 or later:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check --strict dist/*
python -m venv .smoke-venv
.smoke-venv/bin/python -m pip install --no-index --find-links dist nexo-agent-protocol
.smoke-venv/bin/python -c "import nexo, importlib.metadata; assert nexo.__version__ == importlib.metadata.version('nexo-agent-protocol')"
.smoke-venv/bin/python -m nexo --help
```

On Windows, activate `.smoke-venv\Scripts\python.exe` instead. This
inspects the source archive (`.tar.gz`) and pure-Python universal wheel
(`py3-none-any.whl`) independently from any editable installation.
The repository's CI packaging job repeats these steps.

## 2. Configure GitHub protected environments

Repository: https://github.com/edujbarrios/nexo

Go to **Settings → Environments** and create:

- `pypi`: enable **Required reviewers** (manual approval by a maintainer)
  and deployment restrictions allowing release tags matching `v*`, if the
  account's GitHub features support these controls.
- `testpypi`: optionally set reviewers; for a first dry run this can be open.
  The workflow itself requires manual `workflow_dispatch` on `main`.

Keep the workflow permissions minimal. The publishing job alone requests
`id-token: write`; build/test jobs never receive upload credentials.
**Do not store `PYPI_API_TOKEN` secrets**; this uses OIDC Trusted Publishing.

## 3. Register PyPI and TestPyPI Trusted Publishers

Both indices require accounts you control and verified email; enable 2FA
and use separate credentials for the two indices.

Open [PyPI account publishers](https://pypi.org/manage/account/publishing/)
and [TestPyPI account publishers](https://test.pypi.org/manage/account/publishing/).
For a new, unregistered project use **Add a new pending publisher**; for a
project you already own, use its **Manage → Publishing** page instead.

Set the fields **exactly** as follows:

| Field | PyPI | TestPyPI |
|---|---|---|
| PyPI project name | `nexo-agent-protocol` | `nexo-agent-protocol` |
| Owner | `edujbarrios` | `edujbarrios` |
| Repository | `nexo` | `nexo` |
| Workflow name | `release.yml` | `release.yml` |
| Environment name | `pypi` | `testpypi` |

**Check that the distribution name is available** in each index and is
owned by you before relying on publication. A pending publisher does not
reserve the name. If another project already owns it, choose a genuinely
available distribution name; update `pyproject.toml`, publishing docs,
workflows, smoke tests and the new publisher registration together.
Never take over an unrelated project's existing distribution name.

## 4. Test upload without publishing a production release

After `.github/workflows/release.yml` is merged into `main`:

1. Open **Actions → Publish Python SDK → Run workflow**.
2. Select branch `main` and run it.
3. The build job checks wheel/sdist metadata and installs the artifacts.
   The TestPyPI job sends the validated distributions to TestPyPI using OIDC.
4. Check the project on TestPyPI and optionally install using:

   ```bash
   python -m pip install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ nexo-agent-protocol==0.1.0
   ```

Use a fresh virtual environment. TestPyPI is a separate index; package
versions may already exist there and PyPI/TestPyPI do not allow overwriting
released files. To rerun upload tests, publish a *new* valid pre-release
version or use a separate test distribution owned by you.

## 5. Publish to production PyPI by pushing an approved tag

Merge all release changes and verify every CI job and package artifact.
Then choose one release version, for example `0.1.0`, and ensure
`pyproject.toml` and `nexo.__version__` both use the same value.

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "NEXO Python SDK 0.1.0"
git push origin v0.1.0
```

Pushing a `vX.Y.Z` tag from a commit on `main` triggers **Publish Python
SDK**. It verifies the tag equals the package version, builds an isolated
wheel/sdist, checks metadata, installs the wheel, and pauses for an authorized
maintainer to approve the `pypi` environment. It then uploads using PyPI
OIDC short-lived credentials and produces publication attestations. No
upload happens on ordinary commits, pull requests, or merge events.

Validate on https://pypi.org/project/nexo-agent-protocol/ only **after**
the workflow succeeds:

```bash
python -m pip install "nexo-agent-protocol==0.1.0"
python -c "import nexo; print(nexo.__version__)"
nexo --help
```

**Do not create/push the production tag until the trusted publisher exists,
the name is confirmed, and you are ready to publish an immutable version.**

## Failure modes and rollback

- **PyPI says project/name unavailable:** stop, select another unclaimed
  distribution name, and update metadata, workflows and OIDC registration.
- **"invalid-publisher" or OIDC failure:** ensure owner, repository,
  filename `release.yml` and GitHub environment match PyPI settings exactly.
- **Version already exists:** bump the version and tag. Never attempt to
  overwrite or replace an existing release file.
- **CI/package smoke failure:** fix via PR and release a fresh tag only after
  rebuilding and rerunning all checks.
- **Bad published release:** yank it from PyPI, document the issue, and
  release a new fixed version. PyPI artifacts are immutable.
- **Security:** protect `main`, release tags and `release.yml` from
  unauthorized changes; enable environment approvals and review third-party
  Actions before merges. PyPI Trusted Publishing does not prove that the
  source or dependencies are secure.

Reference:
[Official PyPI Trusted Publisher instructions](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[PyPI pending publisher setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
[Python Packaging Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
