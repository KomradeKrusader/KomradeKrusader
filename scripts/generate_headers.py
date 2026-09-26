from pathlib import Path

HEADERS = ["about", "stack", "projects", "stats", "about this page"]
WIDTH = 800
HEIGHT = 24
FONT_SIZE = 13


def make_header_svg(title, out_path):
  
  text_width = len(title) * 8.0
  line_start = text_width + 14

  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: {FONT_SIZE}px; font-weight: 600; fill: #f0f6fc; }}
    line {{ stroke: #21262d; stroke-width: 1; }}
  </style>
  <text x="0" y="16">{title}</text>
  <line x1="{line_start}" y1="12" x2="{WIDTH}" y2="12" />
</svg>"""
  with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)


if __name__ == "__main__":
  assets_dir = Path(__file__).resolve().parent.parent / "assets"
  assets_dir.mkdir(exist_ok=True)
  for name in HEADERS:
    slug = name.replace(" ", "-")
    make_header_svg(name, assets_dir / f"hd-{slug}.svg")
  print("Generated hairline header SVGs in assets/")