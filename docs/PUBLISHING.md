# Publish NEXO to PyPI without GitHub Releases or tags

You can publish the pure-Python **`nexo-agent-protocol`** distribution directly
from GitHub Actions. No GitHub Release, Git tag or permanent PyPI API token
is necessary. Publishing runs **only on manual request** and uses PyPI
Trusted Publishing (OIDC).

NEXO retains its restrictive
[Attribution–NonCommercial–NoDerivatives license](../LICENSE). Publishing on
PyPI does not change these conditions.

## Package identity

- Distribution: `nexo-agent-protocol` (verify that you own or can register
  this name on PyPI; pending publishers do not reserve it).
- Import and CLI: `nexo`; `pip install nexo` is a different project.
- Initial version: `0.1.0`, in `pyproject.toml` and
  `python/nexo/__init__.py`.
- Native `nexo-native` wheels are **not** included in this upload.

## 1. Configure the PyPI Trusted Publisher (once)

On [PyPI Publishing](https://pypi.org/manage/account/publishing/),
register a pending publisher for a new project or add it under your
existing project:

| Field | Exact value |
|---|---|
| PyPI project name | `nexo-agent-protocol` |
| GitHub owner | `edujbarrios` |
| GitHub repository | `nexo` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

In [GitHub Environments](https://github.com/edujbarrios/nexo/settings/environments)
create or verify **`pypi`**. Recommended: configure required reviewer
approval. **Important:** if deployment branch restrictions are enabled,
allow **`main`**; this workflow is dispatched from main, **not from a tag**.

For optional rehearsal using **TestPyPI**, independently register the same
publisher there with environment `testpypi` and create that GitHub
environment. TestPyPI and PyPI accounts are separate.

No `PYPI_API_TOKEN` GitHub secret is needed.

## 2. Publish directly (without a release or tag)

1. Go to **[Actions → Publish Python SDK](https://github.com/edujbarrios/nexo/actions/workflows/release.yml)**.
2. Click **Run workflow** and choose branch **`main`**.
3. Select **`pypi`** from the **`index`** dropdown. (Choose
   `testpypi` for a dry run only if you configured its publisher too.)
4. Click **Run workflow** to start.
5. The `build` job runs tests, builds the wheel and source archive, checks
   metadata and the LICENSE, and installs and validates the build.
6. The **Publish manually to PyPI** job uploads the validated artifacts
   using OIDC. If you protected the `pypi` environment, approve the job.
7. Wait for the publishing **job** to succeed and verify
   [the package on PyPI](https://pypi.org/project/nexo-agent-protocol/).

A green build job alone does **not** confirm that PyPI accepted the upload.
The action must have a Trusted Publisher matching the exact workflow and
environment; the package name must be available or already yours.

Once published:

```bash
python -m pip install nexo-agent-protocol==0.1.0
python -c "import nexo; print(nexo.__version__)"
nexo --help
```

**No GitHub Release, tag, push or merge triggers an upload.** Only the
manual workflow dispatch with an explicit destination does.

## 3. Publish subsequent versions

PyPI does **not** permit overwriting files from an existing version.
For each new upload, update `pyproject.toml` and the SDK's `__version__`
together (for example `0.1.1`), merge the changes to `main`, then
repeat **Actions → Publish Python SDK → Run workflow → pypi**.
A GitHub Release is optional and unrelated.

## 4. Validate locally if desired

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check --strict dist/*
python scripts/check_dist.py
```

The publishing workflow performs the same artifact validations and clean
installation checks automatically.

## Troubleshooting and security

- **PyPI authentication error:** confirm project owner, repository,
  `release.yml`, and `pypi` match the Trusted Publisher registration.
- **GitHub deployment blocked:** allow branch `main` in the environment's
  deployment restrictions rather than only tag patterns.
- **Version already exists:** increment the package version; you cannot
  republish the same files or version.
- **Publishing job skipped:** choose `pypi`, not `testpypi`, and start the
  manual workflow on `main`.
- **PyPI name unavailable:** pick an available distribution name and update
  the metadata, smoke tests, README, publishing workflow and Trusted
  Publisher registration together.
- **Incorrect published version:** yank it on PyPI, fix the code and publish
  a new version. Artifacts are immutable.
- **Security:** protect `main`, review any changes to `release.yml`, require
  manual environment approval where possible, and maintain PyPI 2FA.

See the [official PyPI Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
