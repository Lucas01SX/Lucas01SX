import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from generate_stats import Stats, render


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
    assert svg.count(">0<") == 4


def test_render_value_x_offset():
    s = Stats(year=2024, total_repos=1, total_stars=2, year_contribs=3, year_commits=2)
    svg = render(s)
    assert 'x="180"' in svg   # first column value: PAD(25) + VAL_OFFSET(155)
    assert 'x="415"' in svg   # second column value: COL2_X(260) + VAL_OFFSET(155)


def test_stats_rejects_negative_values():
    with pytest.raises(ValueError):
        Stats(year=2024, total_repos=-1, total_stars=0, year_contribs=0, year_commits=0)


def test_stats_rejects_commits_exceeding_contribs():
    with pytest.raises(ValueError):
        Stats(year=2024, total_repos=1, total_stars=0, year_contribs=5, year_commits=10)


def test_stats_rejects_invalid_year():
    with pytest.raises(ValueError):
        Stats(year=1969, total_repos=0, total_stars=0, year_contribs=0, year_commits=0)
