import json
import pathlib
import re
import sys
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from generate_stats import Stats, fetch, render

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_urlopen_raw(raw: bytes):
    mock_response = MagicMock()
    mock_response.read.return_value = raw
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_response)


def _mock_urlopen(payload: dict):
    return _mock_urlopen_raw(json.dumps(payload).encode())


NOW = datetime(2025, 6, 5, tzinfo=timezone.utc)

VALID_PAYLOAD = {
    "data": {
        "user": {
            "repositories": {
                "totalCount": 7,
                "nodes": [{"stargazerCount": 3}, {"stargazerCount": 1}],
            },
            "contributionsCollection": {
                "totalCommitContributions": 187,
                "contributionCalendar": {"totalContributions": 232},
            },
        }
    }
}

# ---------------------------------------------------------------------------
# render() tests
# ---------------------------------------------------------------------------

def test_render_contains_all_stat_values():
    s = Stats(year=2024, total_repos=12, total_stars=34, year_contribs=567, year_commits=89)
    svg = render(s)
    assert f">{s.total_repos}<" in svg
    assert f">{s.total_stars}<" in svg
    assert f">{s.year_contribs}<" in svg
    assert f">{s.year_commits}<" in svg


def test_render_contains_year_in_title():
    s = Stats(year=2025, total_repos=1, total_stars=0, year_contribs=0, year_commits=0)
    assert "2025" in render(s)


def test_render_is_valid_svg():
    s = Stats(year=2024, total_repos=1, total_stars=0, year_contribs=0, year_commits=0)
    svg = render(s)
    assert svg.strip().startswith("<svg")
    assert svg.strip().endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_render_zero_values():
    s = Stats(year=2024, total_repos=0, total_stars=0, year_contribs=0, year_commits=0)
    svg = render(s)
    assert f">{s.total_repos}<" in svg
    assert f">{s.total_stars}<" in svg
    assert f">{s.year_contribs}<" in svg
    assert f">{s.year_commits}<" in svg


def test_render_two_column_layout():
    s = Stats(year=2024, total_repos=1, total_stars=2, year_contribs=3, year_commits=2)
    svg = render(s)
    x_positions = sorted({int(m) for m in re.findall(r'<text x="(\d+)"', svg)})
    assert len(x_positions) >= 2
    assert x_positions[-1] > x_positions[0]


# ---------------------------------------------------------------------------
# Stats.__post_init__ tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("total_repos", -1),
    ("total_stars", -1),
    ("year_contribs", -1),
    ("year_commits", -1),
])
def test_stats_rejects_negative_values(field, value):
    kwargs = dict(year=2024, total_repos=0, total_stars=0, year_contribs=0, year_commits=0)
    kwargs[field] = value
    with pytest.raises(ValueError):
        Stats(**kwargs)


def test_stats_rejects_commits_exceeding_contribs():
    with pytest.raises(ValueError):
        Stats(year=2024, total_repos=1, total_stars=0, year_contribs=5, year_commits=10)


def test_stats_rejects_invalid_year():
    with pytest.raises(ValueError):
        Stats(year=1969, total_repos=0, total_stars=0, year_contribs=0, year_commits=0)


# ---------------------------------------------------------------------------
# fetch() tests
# ---------------------------------------------------------------------------

def test_fetch_happy_path():
    with (
        patch("urllib.request.urlopen", _mock_urlopen(VALID_PAYLOAD)),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
    ):
        stats = fetch(NOW)
    assert stats == Stats(year=2025, total_repos=7, total_stars=4, year_contribs=232, year_commits=187)


def test_fetch_raises_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        fetch(NOW)


def test_fetch_raises_on_graphql_errors():
    payload = {"errors": [{"message": "Could not resolve to a User"}]}
    with (
        patch("urllib.request.urlopen", _mock_urlopen(payload)),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="Could not resolve"),
    ):
        fetch(NOW)


def test_fetch_raises_on_null_data():
    payload = {"data": None}
    with (
        patch("urllib.request.urlopen", _mock_urlopen(payload)),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="null 'data'"),
    ):
        fetch(NOW)


def test_fetch_raises_on_null_user():
    payload = {"data": {"user": None}}
    with (
        patch("urllib.request.urlopen", _mock_urlopen(payload)),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="null for user"),
    ):
        fetch(NOW)


def test_fetch_raises_on_missing_field():
    payload = {"data": {"user": {"repositories": {"totalCount": 1, "nodes": []}}}}
    with (
        patch("urllib.request.urlopen", _mock_urlopen(payload)),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="API schema may have changed"),
    ):
        fetch(NOW)


def test_fetch_raises_on_http_error():
    http_error = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)
    with (
        patch("urllib.request.urlopen", side_effect=http_error),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="HTTP 401"),
    ):
        fetch(NOW)


def test_fetch_raises_on_url_error():
    url_error = urllib.error.URLError(reason="Connection refused")
    with (
        patch("urllib.request.urlopen", side_effect=url_error),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="Failed to reach"),
    ):
        fetch(NOW)


def test_fetch_raises_on_invalid_json():
    with (
        patch("urllib.request.urlopen", _mock_urlopen_raw(b"not json")),
        patch.dict("os.environ", {"GITHUB_TOKEN": "fake"}),
        pytest.raises(RuntimeError, match="non-JSON"),
    ):
        fetch(NOW)
