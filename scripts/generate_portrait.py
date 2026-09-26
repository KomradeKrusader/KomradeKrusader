import base64
import cv2
import numpy as np
from PIL import Image
from rembg import remove
import io

RAMP = " .`:-=+*cs#%@"
COLS = 120
ROW_ASPECT = 0.48  # Monospace char height vs width compensation
FONT_SIZE = 12.9
CHAR_W = 7.74  # 0.600em * 12.9
LINE_H = 15.0


def process_image(img_path):
  # remove the background
  with open(img_path, "rb") as f:
    nobg = Image.open(io.BytesIO(remove(f.read()))).convert("RGBA")

  # fill transparent areas with pure white
  canvas = Image.new("RGBA", nobg.size, (255, 255, 255, 255))
  canvas.paste(nobg, mask=nobg.split()[3])
  rgb = np.array(canvas.convert("RGB"))

  # resize to grid
  h, w, _ = rgb.shape
  rows = int(COLS * (h / w) * ROW_ASPECT)
  resized = cv2.resize(rgb, (COLS, rows), interpolation=cv2.INTER_AREA)

  # bilateral filter & CLAHE
  gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
  smooth = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
  clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
  enhanced = clahe.apply(smooth)

  # gamma darkening curve (v/255)^1.7
  darkened = np.power(enhanced / 255.0, 1.7) * 255.0
  darkened = np.clip(darkened, 0, 255).astype(np.uint8)

  # map to ramp
  ascii_lines = []
  ramp_len = len(RAMP)
  for row in darkened:
    line = "".join([RAMP[int((val / 255.0) * (ramp_len - 1))] for val in row])
    ascii_lines.append(line)

  return ascii_lines, rows


def generate_svg(ascii_lines, rows, woff2_path, out_svg):
  with open(woff2_path, "rb") as f:
    b64_font = base64.b64encode(f.read()).decode("utf-8")

  svg_w = int(COLS * CHAR_W)
  svg_h = int(rows * LINE_H)

  # generate SMIL animated wipe per row
  defs_clips = []
  text_elements = []

  for i, line in enumerate(ascii_lines):
    y = int((i + 1) * LINE_H)
    delay = f"{i * 0.09:.2f}s"
    clip_id = f"row-clip-{i}"

    defs_clips.append(f"""
      <clipPath id="{clip_id}">
        <rect x="0" y="{y - int(LINE_H)}" width="0" height="{int(LINE_H)}">
          <animate attributeName="width" from="0" to="{svg_w}" dur="0.25s" begin="{delay}" fill="freeze" />
        </rect>
      </clipPath>
    """)

    text_elements.append(
        f'<text x="0" y="{y}" clip-path="url(#{clip_id})">{line}</text>'
    )

  svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">
  <style>
    @font-face {{
      font-family: 'JetBrainsMono';
      src: url('data:font/woff2;base64,{b64_font}') format('woff2');
      font-weight: normal;
      font-style: normal;
    }}
    text {{
      font-family: 'JetBrainsMono', monospace;
      font-size: {FONT_SIZE}px;
      fill: #c9d1d9;
      white-space: pre;
    }}
  </style>
  <defs>
    {"".join(defs_clips)}
  </defs>
  {"".join(text_elements)}
</svg>"""

  with open(out_svg, "w", encoding="utf-8") as f:
    f.write(svg_content)

from pathlib import Path

if __name__ == "__main__":
  # resolve paths relative to the repository root, doesn't matter where it's run from
  repo_root = Path(__file__).resolve().parent.parent

  # checks for either input.jpg or input.jpeg
  input_path = repo_root / "assets" / "input.jpeg"
  if not input_path.exists():
    input_path = repo_root / "assets" / "input.jpg"
  if not input_path.exists():
      input_path = repo_root / "assets" / "input.png"

  font_path = repo_root / "fonts" / "ramp.woff2"
  output_svg = repo_root / "portrait.svg"

  print(f"[1/3] Reading input image from: {input_path}")
  print("[2/3] Removing background via rembg...")
  lines, rows = process_image(str(input_path))

  print(f"[3/3] Generating animated SVG to: {output_svg}")
  generate_svg(lines, rows, str(font_path), str(output_svg))
  print("Done!")