"""
Generate a simple icon.ico for the app (a barcode-style icon).
Creates a 256x256 icon, 128, 64, 48, 32, 16 multi-size .ico.
"""
import os
from PIL import Image, ImageDraw, ImageFont

def make_icon(out_path: str):
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for sz in sizes:
        img = Image.new('RGBA', (sz, sz), (245, 245, 247, 255))
        draw = ImageDraw.Draw(img)
        pad = max(1, sz // 16)
        # Blue header band
        draw.rectangle([pad, pad, sz - pad, pad + sz // 6], fill=(26, 77, 143, 255))
        # Barcode bars (black) below header
        bar_top = pad + sz // 5
        bar_bot = sz - pad - sz // 4
        x = pad * 2
        widths = [2, 1, 3, 1, 2, 1, 4, 1, 2, 2, 1, 3, 1, 2, 1, 4]
        i = 0
        while x < sz - pad * 2 and i < len(widths) * 2:
            w = widths[i % len(widths)] * max(1, sz // 64)
            if i % 2 == 0:
                draw.rectangle([x, bar_top, x + w, bar_bot], fill=(0, 0, 0, 255))
            x += w + max(1, sz // 64)
            i += 1
        # Bottom band (numbers text)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                       max(8, sz // 8))
        except Exception:
            font = ImageFont.load_default()
        text = "EAN-13"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (sz - tw) // 2
        ty = sz - pad - th - 2
        draw.text((tx, ty), text, fill=(26, 77, 143, 255), font=font)
        images.append(img)
    # Save as multi-size ICO - use the largest as base, then append smaller
    # PIL ICO writer takes sizes param to control output sizes
    base = images[-1]  # 256x256
    base.save(out_path, format='ICO',
               sizes=[(sz, sz) for sz in sizes])


if __name__ == '__main__':
    out = '/home/z/my-project/barcode-generator/assets/icon.ico'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    make_icon(out)
    print(f"Saved: {out}")
    # Verify
    im = Image.open(out)
    print(f"Icon size: {im.size}")
