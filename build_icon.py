#!/usr/bin/env python3
"""
Generate high-fidelity app icon and favicons in SVG, PNG, and ICO formats,
replicating the stock chart icon requested by the user.
"""

import os
from PIL import Image, ImageDraw

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# 1. Generate crisp SVG vector
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#557bff"/>
      <stop offset="45%" stop-color="#3d63f8"/>
      <stop offset="100%" stop-color="#2a4be2"/>
    </linearGradient>
    <filter id="shadow" x="-8%" y="-8%" width="116%" height="116%">
      <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#0f2b96" flood-opacity="0.3"/>
    </filter>
  </defs>
  
  <!-- Outer Blue Squircle Background -->
  <rect x="4" y="4" width="120" height="120" rx="30" fill="url(#bgGrad)" filter="url(#shadow)"/>
  
  <!-- Inner White Chart Box -->
  <rect x="26" y="26" width="76" height="76" rx="6" fill="#ffffff"/>
  
  <!-- Grid Lines (Vertical) -->
  <line x1="41.2" y1="26" x2="41.2" y2="102" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="56.4" y1="26" x2="56.4" y2="102" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="71.6" y1="26" x2="71.6" y2="102" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="86.8" y1="26" x2="86.8" y2="102" stroke="#e2e8f0" stroke-width="1.8"/>
  
  <!-- Grid Lines (Horizontal) -->
  <line x1="26" y1="41.2" x2="102" y2="41.2" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="26" y1="56.4" x2="102" y2="56.4" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="26" y1="71.6" x2="102" y2="71.6" stroke="#e2e8f0" stroke-width="1.8"/>
  <line x1="26" y1="86.8" x2="102" y2="86.8" stroke="#e2e8f0" stroke-width="1.8"/>
  
  <!-- Ascending Stock Trend Line (Vibrant Red) -->
  <polyline points="32,94 48,68 62,80 96,36" 
            fill="none" 
            stroke="#ef4444" 
            stroke-width="5.5" 
            stroke-linecap="round" 
            stroke-linejoin="round"/>
</svg>
"""

svg_path = os.path.join(STATIC_DIR, "favicon.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content.strip())
print(f"✓ Saved SVG to {svg_path}")


# 2. Draw high-res master PNG (512x512 supersampled)
SIZE = 512
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Blue squircle background with vertical gradient
# Draw rounded rectangle
r = 120
for y in range(SIZE):
    # interpolate color from #557bff (85, 123, 255) to #2a4be2 (42, 75, 226)
    ratio = y / SIZE
    red = int(85 + (42 - 85) * ratio)
    green = int(123 + (75 - 123) * ratio)
    blue = int(255 + (226 - 255) * ratio)
    # Mask by squircle shape
# A simpler, clean way: draw rounded rectangle on mask
mask = Image.new("L", (SIZE, SIZE), 0)
mask_draw = ImageDraw.Draw(mask)
margin = 20
mask_draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=110, fill=255)

grad = Image.new("RGBA", (SIZE, SIZE))
for y in range(SIZE):
    ratio = y / SIZE
    c = (int(85 * (1 - ratio) + 42 * ratio), int(123 * (1 - ratio) + 75 * ratio), int(255 * (1 - ratio) + 226 * ratio), 255)
    for x in range(SIZE):
        grad.putpixel((x, y), c)

img.paste(grad, (0, 0), mask=mask)

# White chart box inside
chart_draw = ImageDraw.Draw(img)
c_margin = 110
chart_rect = [c_margin, c_margin, SIZE - c_margin, SIZE - c_margin]
chart_draw.rounded_rectangle(chart_rect, radius=24, fill=(255, 255, 255, 255))

# Grid lines inside chart box
cols = 5
step = (SIZE - 2 * c_margin) / cols
for i in range(1, cols):
    x = int(c_margin + i * step)
    chart_draw.line([(x, c_margin), (x, SIZE - c_margin)], fill=(226, 232, 240, 255), width=6)

for i in range(1, cols):
    y = int(c_margin + i * step)
    chart_draw.line([(c_margin, y), (SIZE - c_margin, y)], fill=(226, 232, 240, 255), width=6)

# Ascending red trend line
# Points: (135, 370), (200, 270), (255, 320), (385, 145)
points = [
    (int(c_margin + 25), int(SIZE - c_margin - 30)),
    (int(c_margin + 90), int(c_margin + 160)),
    (int(c_margin + 145), int(c_margin + 210)),
    (int(SIZE - c_margin - 25), int(c_margin + 35)),
]
chart_draw.line(points, fill=(239, 68, 68, 255), width=22, joint="round")

# Save PNG at 128x128 and 64x64
png_128 = img.resize((128, 128), Image.Resampling.LANCZOS)
png_path = os.path.join(STATIC_DIR, "favicon.png")
png_128.save(png_path)
print(f"✓ Saved PNG to {png_path}")

# Save multi-size ICO
ico_path = os.path.join(STATIC_DIR, "favicon.ico")
img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print(f"✓ Saved ICO to {ico_path}")
