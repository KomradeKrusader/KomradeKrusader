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
        "Warning: GITHUB_TOKEN not set. Using local sample data for preview."
    )
    # 52 dummy weeks for testing local visualization
    dummy_weeks = [0] * 40 + [2, 0, 1, 0, 4, 1, 0, 0, 3, 1, 0, 2]
    return {
        "total": 14,
        "active_days": 8,
        "best_week": 4,
        "weekly_counts": dummy_weeks,
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

  cal = user_data["contributionsCollection"]["contributionCalendar"]
  total = cal["totalContributions"]

  weekly_counts = []
  active_days = 0
  for week in cal["weeks"]:
    week_sum = 0
    for day in week["contributionDays"]:
      count = day["contributionCount"]
      week_sum += count
      if count > 0:
        active_days += 1
    weekly_counts.append(week_sum)

  best_week = max(weekly_counts) if weekly_counts else 0

  # Language data
  lang_bytes = defaultdict(int)
  repo_counts = defaultdict(int)
  for repo in user_data["repositories"]["nodes"]:
    for edge in repo["languages"]["edges"]:
      name = edge["node"]["name"]
      lang_bytes[name] += edge["size"]
      repo_counts[name] += 1

  return {
      "total": total,
      "active_days": active_days,
      "best_week": best_week,
      "weekly_counts": weekly_counts,
      "bytes": dict(lang_bytes),
      "repos": dict(repo_counts),
  }


def generate_sparkline_path(weekly_counts, width=700, y_base=160, y_top=100):
  if not weekly_counts:
    return "", 0, y_base

  n = len(weekly_counts)
  max_val = max(weekly_counts) if max(weekly_counts) > 0 else 1

  # Compute coordinates for each week
  points = []
  for i, count in enumerate(weekly_counts):
    x = (i / (n - 1)) * width
    # Scale inverted since SVG y increases downwards
    y = y_base - (count / max_val) * (y_base - y_top)
    points.append((round(x, 1), round(y, 1)))

  # Smooth Bézier path interpolation
  path_cmds = [f"M {points[0][0]} {points[0][1]}"]
  for i in range(len(points) - 1):
    p0 = points[i]
    p1 = points[i + 1]
    dx = p1[0] - p0[0]
    cp1_x = round(p0[0] + dx * 0.45, 1)
    cp2_x = round(p1[0] - dx * 0.45, 1)
    path_cmds.append(f"C {cp1_x} {p0[1]}, {cp2_x} {p1[1]}, {p1[0]} {p1[1]}")

  return " ".join(path_cmds), points[-1][0], points[-1][1]


def render_stats_svg(data, out_path):
  width = 700
  height = 180
  y_base = 160

  path_d, last_x, last_y = generate_sparkline_path(
      data["weekly_counts"], width=width, y_base=y_base, y_top=95
  )

  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .hero {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 54px; font-weight: 700; fill: #f0f6fc; }}
    .sub {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 13px; fill: #8b949e; letter-spacing: 0.02em; }}
    .metric-num {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 24px; font-weight: 700; fill: #f0f6fc; }}
    .metric-lbl {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 11px; fill: #8b949e; }}
  </style>

  <!-- Left: Hero number & label -->
  <text x="0" y="52" class="hero">{data['total']}</text>
  <text x="0" y="76" class="sub">contributions in the last year</text>

  <!-- Right: Secondary metrics -->
  <text x="{width}" y="30" text-anchor="end" class="metric-num">{data['active_days']}</text>
  <text x="{width}" y="45" text-anchor="end" class="metric-lbl">active days</text>

  <text x="{width}" y="76" text-anchor="end" class="metric-num">{data['best_week']}</text>
  <text x="{width}" y="91" text-anchor="end" class="metric-lbl">best week</text>

  <!-- Sparkline & Base Rule -->
  <line x1="0" y1="{y_base}" x2="{width}" y2="{y_base}" stroke="#21262d" stroke-width="1.5" />
  <path d="{path_d}" fill="none" stroke="#e6edf3" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
  <circle cx="{last_x}" cy="{last_y}" r="3.5" fill="#f0f6fc" />
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
  render_stats_svg(data, str(stats_file))
  render_langs_svg(data["bytes"], data["repos"], str(langs_file))
  print("Updated stats.svg (with sparkline) and langs.svg")