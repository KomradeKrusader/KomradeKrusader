from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.request

# The workflow passes GITHUB_TOKEN automatically; fallback to GH_LOGIN or your username
TOKEN = os.environ.get("GITHUB_TOKEN")
USER = os.environ.get("GH_LOGIN", "KomradeKrusader")

# 1. Pinned UTC Date Boundaries (Avoids shifting sparkline positions between runs)
now = datetime.now(timezone.utc)
to_date = now.strftime("%Y-%m-%dT23:59:59Z")
from_date = datetime(now.year - 1, now.month, now.day).strftime(
    "%Y-%m-%dT00:00:00Z"
)

# 2. GraphQL Query with 'privacy: PUBLIC' filter
query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, isFork: false) {
      nodes {
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""


def fetch_data():
  # When running locally without a token, use a minimal dummy response or pass your GH CLI token
  if not TOKEN:
    print(
        "Warning: GITHUB_TOKEN environment variable not set. Using fallback"
        " values for local preview."
    )
    return {"totalContributions": 10}

  req = urllib.request.Request(
      "https://api.github.com/graphql",
      data=json.dumps({
          "query": query,
          "variables": {"login": USER, "from": from_date, "to": to_date},
      }).encode("utf-8"),
      headers={
          "Authorization": f"Bearer {TOKEN}",
          "Content-Type": "application/json",
          "User-Agent": "Stats-Generator",
      },
  )
  with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    if "errors" in result:
      raise RuntimeError(f"GitHub GraphQL error: {result['errors']}")
    return result["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]


def render_stats_svg(total_contribs, out_path):
  # Generates a minimal, clean stat badge styled for dark/light profile pages
  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="340" height="70" viewBox="0 0 340 70">
  <style>
    .label {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 11px; fill: #8b949e; letter-spacing: 0.05em; }}
    .num {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 24px; font-weight: bold; fill: #58a6ff; }}
  </style>
  <text x="10" y="24" class="label">CONTRIBUTIONS (PAST YEAR)</text>
  <text x="10" y="56" class="num">{total_contribs}</text>
</svg>"""
  with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)


if __name__ == "__main__":
  repo_root = Path(__file__).resolve().parent.parent
  out_file = repo_root / "stats.svg"

  calendar = fetch_data()
  total = calendar.get("totalContributions", 0)
  render_stats_svg(total, str(out_file))
  print(f"Generated stats.svg ({total} total contributions)")