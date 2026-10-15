"""Offline unit tests for automatic PyPI upload decision and fail-closed policy."""
import io
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest

from scripts.pypi_preflight import (
    PROJECT_NAME, package_version, publication_target, version_exists,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse(io.BytesIO):
    status = 200


def test_push_main_targets_production_index():
    assert publication_target("push", "refs/heads/main", "") == "pypi"
    assert publication_target("workflow_dispatch", "refs/heads/main", "pypi") == "pypi"
    assert publication_target("workflow_dispatch", "refs/heads/main", "testpypi") == "testpypi"


@pytest.mark.parametrize("event,ref,index", [
    ("push", "refs/heads/other", ""),
    ("push", "refs/tags/v0.1.0", ""),
    ("workflow_dispatch", "refs/heads/dev", "pypi"),
    ("workflow_dispatch", "refs/heads/main", "external"),
    ("pull_request", "refs/heads/main", "pypi"),
])
def test_refuses_untrusted_context(event, ref, index):
    with pytest.raises(ValueError):
        publication_target(event, ref, index)


def test_nonexistent_version_returns_false_without_guessing():
    def missing(request, timeout):
        assert request.full_url == (
            "https://pypi.org/pypi/nexo-agent-protocol/0.1.0/json"
        )
        assert timeout == 20
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    assert version_exists("pypi", "0.1.0", opener=missing) is False


def test_existing_version_skips_upload():
    payload = b'{"info":{"name":"nexo-agent-protocol","version":"0.1.0"}}'
    def existing(request, timeout):
        assert request.full_url.startswith("https://test.pypi.org/pypi/")
        return FakeResponse(payload)

    assert version_exists("testpypi", "0.1.0", opener=existing)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502])
def test_non404_http_errors_fail_closed(status):
    def failure(request, timeout):
        raise HTTPError(request.full_url, status, "Failure", None, None)
    with pytest.raises(RuntimeError, match="refusing to publish"):
        version_exists("pypi", "0.1.0", opener=failure)


def test_network_failure_fails_closed():
    def offline(request, timeout):
        raise URLError("network unavailable")
    with pytest.raises(URLError):
        version_exists("pypi", "0.1.0", opener=offline)


def test_unexpected_pypi_response_fails_closed():
    for body in (
        b'{"info":{"name":"other-project","version":"0.1.0"}}',
        b'{"info":{"name":"nexo-agent-protocol","version":"9.9.9"}}',
        b"not valid json",
    ):
        with pytest.raises((RuntimeError, ValueError)):
            version_exists("pypi", "0.1.0",
                           opener=lambda req, timeout: FakeResponse(body))


def test_reject_invalid_version_or_target():
    for version in ("", "1.0.0/../../etc", "main", "0.1.0.dev0"):
        with pytest.raises(ValueError):
            version_exists("pypi", version)
    with pytest.raises(ValueError):
        version_exists("unknown", "0.1.0")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="release job uses Python 3.12 tomllib")
def test_sdk_version_matches_pyproject():
    assert package_version(ROOT) == "0.1.0"
