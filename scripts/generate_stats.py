import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, fields
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "Lucas01SX")
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# totalCount is unaffected by pagination. total_stars is a lower bound: it
# aggregates stargazerCount over the first 100 nodes (ordered by descending star
# count), so any repo beyond the 100-node cap is excluded regardless of its star count.
QUERY = """
{
  user(login: "%s") {
    repositories(
      ownerAffiliations: OWNER
      isFork: false
      first: 100
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection(from: "%sT00:00:00Z", to: "%sT23:59:59Z") {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


@dataclass(frozen=True)
class Stats:
    year: int           # calendar year this snapshot covers
    total_repos: int    # lifetime, all owned non-fork repos
    total_stars: int    # lifetime, lower bound (100-repo API cap, top-starred first)
    year_contribs: int  # current calendar year, all contribution types
    year_commits: int   # current calendar year, commits only (subset of year_contribs)

    def __post_init__(self) -> None:
        if any(getattr(self, f.name) < 0 for f in fields(self)):
            raise ValueError(f"Stats fields must be non-negative: {self}")
        if self.year < 1970:
            raise ValueError(f"year must be a valid calendar year (≥ 1970), got: {self.year}")
        if self.year_commits > self.year_contribs:
            raise ValueError(
                f"year_commits ({self.year_commits}) cannot exceed "
                f"year_contribs ({self.year_contribs})"
            )


def fetch(now: datetime) -> Stats:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Configure the secret in repository settings "
            "and ensure the workflow step sets it via "
            "env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}"
        )
    query = QUERY % (USERNAME, f"{now.year}-01-01", now.strftime("%Y-%m-%d"))
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"GitHub API returned HTTP {e.code}. Verify GITHUB_TOKEN is valid and has required scopes."
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Failed to reach GitHub API: {e.reason}. Check network connectivity."
        ) from e
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"GitHub API returned non-JSON. "
            f"Response (first 500 chars): {raw[:500].decode(errors='replace')}"
        ) from e
    if "errors" in payload:
        msgs = [err.get("message", str(err)) for err in payload["errors"]]
        raise RuntimeError("; ".join(msgs))
    data = payload.get("data")
    if data is None:
        raise RuntimeError("GitHub API returned null 'data'. Check GITHUB_TOKEN scopes.")
    user = data.get("user")
    if user is None:
        raise RuntimeError(
            f"GitHub API returned null for user '{USERNAME}'. "
            "Verify the USERNAME constant and that GITHUB_TOKEN has 'read:user' scope."
        )
    try:
        repos_data = user["repositories"]
        contribs_data = user["contributionsCollection"]
        total_repos = repos_data["totalCount"]
        nodes = repos_data["nodes"]
        if not isinstance(nodes, list):
            raise RuntimeError(
                f"Expected 'nodes' to be a list, got {type(nodes).__name__}. "
                "The API schema may have changed."
            )
        total_stars = sum(r["stargazerCount"] for r in nodes)
        year_contribs = contribs_data["contributionCalendar"]["totalContributions"]
        year_commits = contribs_data["totalCommitContributions"]
    except KeyError as e:
        raise RuntimeError(
            f"GitHub API response is missing expected field {e}. "
            "The API schema may have changed."
        ) from e
    return Stats(
        year=now.year,
        total_repos=total_repos,
        total_stars=total_stars,
        year_contribs=year_contribs,
        year_commits=year_commits,
    )


def _xml_escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(stats: Stats) -> str:
    BG, BORDER = "#1a1b27", "#2d3149"
    TITLE, TEXT, VALUE = "#70a5fd", "#a9b1d6", "#e0af68"
    FONT = "'Segoe UI', 'Liberation Sans', sans-serif"

    W, H = 495, 155
    PAD = 25
    COL2_X = 260
    VAL_OFFSET = 155
    DIVIDER_Y = 46
    TITLE_Y = 32
    ROW1_Y = 82
    ROW2_Y = 122

    def cell(x, y, label, val):
        return (
            f'<text x="{x}" y="{y}" fill="{TEXT}" font-size="13">{_xml_escape(label)}</text>'
            f'<text x="{x + VAL_OFFSET}" y="{y}" fill="{VALUE}" font-size="13" font-weight="600">{_xml_escape(val)}</text>'
        )

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" rx="6" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
  <line x1="{PAD}" y1="{DIVIDER_Y}" x2="{W - PAD}" y2="{DIVIDER_Y}" stroke="{BORDER}" stroke-width="1"/>
  <g font-family="{FONT}">
    <text x="{PAD}" y="{TITLE_Y}" fill="{TITLE}" font-size="14" font-weight="600">GitHub Stats — {_xml_escape(stats.year)}</text>
    {cell(PAD, ROW1_Y, "Contribuições", stats.year_contribs)}{cell(COL2_X, ROW1_Y, "Commits", stats.year_commits)}
    {cell(PAD, ROW2_Y, "Repositórios", stats.total_repos)}{cell(COL2_X, ROW2_Y, "Stars", stats.total_stars)}
  </g>
</svg>"""


def main() -> None:
    output_dir = REPO_ROOT / "assets"
    try:
        output_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Failed to create output directory '{output_dir}': {e}") from e
    now = datetime.now(timezone.utc)
    stats = fetch(now)
    svg = render(stats)
    output_path = output_dir / "stats.svg"
    try:
        output_path.write_text(svg, encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write SVG to '{output_path}': {e}") from e
    print(f"{output_path} generated ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
