from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN")
USER = os.environ.get("GH_LOGIN", "KomradeKrusader")

now = datetime.now(timezone.utc)
to_date = now.strftime("%Y-%m-%dT23:59:59Z")
from_date = datetime(now.year - 1, now.month, now.day).strftime(
    "%Y-%m-%dT00:00:00Z"
)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
      }
    }
    repositories(first: 100, privacy: PUBLIC, isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
  }
}
"""


def fetch_data():
  if not TOKEN:
    print(
        "Warning: GITHUB_TOKEN not set. Generating sample fallback preview data."
    )
    return {
        "total": 10,
        "bytes": {"JavaScript": 65000, "Python": 25000, "C++": 10000},
        "repos": {"JavaScript": 1, "Python": 1, "C++": 1},
    }

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
    data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
      raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
    user_data = data["data"]["user"]

  total = user_data["contributionsCollection"]["contributionCalendar"][
      "totalContributions"
  ]

  lang_bytes = defaultdict(int)
  repo_counts = defaultdict(int)

  for repo in user_data["repositories"]["nodes"]:
    for edge in repo["languages"]["edges"]:
      name = edge["node"]["name"]
      lang_bytes[name] += edge["size"]
      repo_counts[name] += 1

  return {
      "total": total,
      "bytes": dict(lang_bytes),
      "repos": dict(repo_counts),
  }


def render_stats_svg(total_contribs, out_path):
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


def render_langs_svg(lang_bytes, repo_counts, out_path):
  total_bytes = sum(lang_bytes.values()) or 1
  top_bytes = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:5]
  top_repos = sorted(repo_counts.items(), key=lambda x: x[1], reverse=True)[:5]

  max_repo = top_repos[0][1] if top_repos else 1
  BAR_MAX_W = 140

  def make_rows(items, is_bytes=True):
    rows = []
    for i, (name, val) in enumerate(items):
      y = 48 + i * 26
      if is_bytes:
        pct = int((val / total_bytes) * 100)
        bar_w = int((val / total_bytes) * BAR_MAX_W)
        val_str = f"{pct}%"
      else:
        bar_w = int((val / max_repo) * BAR_MAX_W)
        val_str = str(val)

      rows.append(f"""
        <text x="0" y="{y}" class="name">{name.lower()}</text>
        <rect x="95" y="{y - 10}" width="{max(bar_w, 4)}" height="8" rx="4" class="bar" />
        <text x="245" y="{y}" class="val">{val_str}</text>
      """)
    return "".join(rows)

  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" viewBox="0 0 600 180">
  <style>
    .hdr {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 10px; fill: #8b949e; letter-spacing: 0.08em; }}
    .name {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 12px; fill: #c9d1d9; }}
    .bar {{ fill: #30363d; }}
    .val {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 11px; fill: #8b949e; }}
  </style>
  <text x="0" y="15" class="hdr">BY BYTES</text>
  {make_rows(top_bytes, is_bytes=True)}
  <g transform="translate(300, 0)">
    <text x="0" y="15" class="hdr">BY REPOS</text>
    {make_rows(top_repos, is_bytes=False)}
  </g>
</svg>"""
  with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)


if __name__ == "__main__":
  repo_root = Path(__file__).resolve().parent.parent
  stats_file = repo_root / "stats.svg"
  langs_file = repo_root / "langs.svg"

  data = fetch_data()
  render_stats_svg(data["total"], str(stats_file))
  render_langs_svg(data["bytes"], data["repos"], str(langs_file))
  print(f"Generated stats.svg and langs.svg in {repo_root}")