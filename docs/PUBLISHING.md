# Automatic PyPI publishing for the NEXO Python SDK

NEXO publishes its **pure-Python** `nexo-agent-protocol` distribution through
GitHub Actions **without creating a GitHub Release, tag or PyPI API token**.
The production upload is attempted automatically when a new, unpublished
package version is merged into `main`. The PyPI Trusted Publisher controls
the actual upload, and the GitHub `pypi` environment can require approval.

The code is source-available under the restrictive
[Attribution–NonCommercial–NoDerivatives license](../LICENSE).
PyPI distribution does not change its permitted uses.

## Package identity

- PyPI distribution: `nexo-agent-protocol` (must be registered to you or
  available; pending publishers do **not** reserve the name).
- Import/CLI: `nexo`; `pip install nexo` belongs to another project.
- Initial version: `0.1.0` in `pyproject.toml` and the SDK's
  `__version__`.
- Optional `nexo-native` Rust extension is not part of this release.
  It requires a separate multiplatform publishing pipeline.

## 1. Configure Trusted Publishing once

In [PyPI Publishing](https://pypi.org/manage/account/publishing/),
register a **pending Trusted Publisher** if the project is new, or add a
publisher to an existing project you control:

| Field | Exact value |
|---|---|
| PyPI project name | `nexo-agent-protocol` |
| GitHub owner | `edujbarrios` |
| GitHub repository | `nexo` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

Create/verify the matching environment under
[GitHub Settings → Environments](https://github.com/edujbarrios/nexo/settings/environments).
**Allow deployments from branch `main`** if branch restrictions are on.
Protect that environment with required reviewers if you want a person to
approve uploads before PyPI receives them. The release workflow's upload
job requests short-lived OIDC credentials; it does not need secrets or a
long-lived PyPI API token.

For an optional dry run, separately configure TestPyPI with the same
owner/repository/workflow but an environment `testpypi`. TestPyPI and
production PyPI are independent registries.

## 2. How automatic publishing works

Merging changes to `main` affecting any of these paths starts
[Publish Python SDK](https://github.com/edujbarrios/nexo/actions/workflows/release.yml):

- `python/**`: public Python SDK implementation;
- `pyproject.toml`: package name, version and metadata;
- `.github/workflows/release.yml`: publication workflow.

The workflow then:

1. Verifies it is running against `main` and that the SDK version matches
   the distribution version.
2. Queries the **version-specific official PyPI JSON API**.
   If that version already exists, **skips the upload**; a network/API
   error (other than HTTP 404) **fails closed** rather than guessing.
3. If the version is new, runs Python tests, builds the wheel and source
   archive, checks their metadata/license, installs the built wheel in an
   isolated environment, and rebuilds a wheel from the source archive.
4. The production job obtains its own short-lived OIDC credential for
   the dedicated `pypi` environment and attempts the upload.
5. Check that **Publish new versions to PyPI** succeeds and confirm the
   package's version on
   [PyPI](https://pypi.org/project/nexo-agent-protocol/).

**A green CI/build job does not prove publication.** PyPI still decides
whether the Trusted Publisher is authorized and the chosen project name
is available. With GitHub environment reviewers, publishing will pause
for their approval.

Subsequent pushes that do not change any of the paths above do not trigger
publishing. A push that changes SDK code but **does not bump the version**
will be skipped because PyPI releases are immutable.

## 3. Publishing later versions

For version `0.1.1` or higher:

1. Change the version in both `pyproject.toml` and
   `python/nexo/__init__.py`.
2. Merge the tested changes into `main`.
3. The workflow automatically checks PyPI and attempts the upload only
   for the new version.

**No GitHub Release or tag is required.**

## 4. Optional manual retries or TestPyPI testing

From [Actions → Publish Python SDK](https://github.com/edujbarrios/nexo/actions/workflows/release.yml),
choose **Run workflow**, branch `main` and select the `index`:
`pypi` for production or `testpypi` for the separate test registry.
By default this is set to safer `testpypi`. Both choices use the same
version-check safeguards and require their respective trusted publisher.

## 5. Dynamic README badges

The README uses the dynamic
[PyPI version badge](https://img.shields.io/pypi/v/nexo-agent-protocol)
and [supported Python versions badge](https://img.shields.io/pypi/pyversions/nexo-agent-protocol).
After PyPI accepts a release, these badges **update automatically** from
PyPI's public data; no GitHub commit, extra bot, PyPI password or workflow
with write permissions is necessary. Badge caches may delay the displayed
version briefly. Before the initial release, an unavailable-package status
is expected. Don't hardcode success or a release version in the README.

## 6. Verify or troubleshoot publication

Production install, only after PyPI has accepted the upload:

```bash
python -m pip install nexo-agent-protocol
python -c "import nexo; print(nexo.__version__)"
nexo --help
```

Build locally to examine artifacts:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check --strict dist/*
python scripts/check_dist.py
```

If publication is blocked:

- **invalid-publisher:** confirm `edujbarrios/nexo`, the exact file
  `release.yml`, and the environment `pypi` in the PyPI registration.
- **Environment approval pending:** review/approve the `pypi` GitHub
  deployment; GitHub branch restrictions must permit `main`.
- **PyPI index unreachable:** the preflight fails and publishes nothing;
  retry the manual workflow once network service recovers.
- **Version already published:** this is normal; bump the version in both
  files for the next release. PyPI files cannot be overwritten.
- **Name unavailable/owned by someone else:** stop and select a different
  distribution name, updating metadata, tests and the publisher together.
- **Upload failed after build:** inspect the *publish* job logs, not only
  the build result. Once the cause is corrected, use manual dispatch for
  a retry of the unpublished version.
- **Unexpected/bad published version:** yank it on PyPI, fix the code and
  publish a new package version.
- **Security:** protect `main`, review workflow and dependency changes,
  keep `pypi` approval active where available, and secure the PyPI account
  with 2FA. OIDC publishing grants real upload authority to this workflow.

Official references:
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [GitHub OIDC for PyPI](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-pypi).
