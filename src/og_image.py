"""
The share card: a 1200x630 PNG with the headline numbers, referenced by og:image.

Best-effort in the same way as the injury report. A link pasted into iMessage, Reddit or
X used to show no preview at all, which is the whole reason a tracker like this spreads
or doesn't; if Pillow or a font is missing the build still publishes, just without it.
"""
import json, os, sys


def _font(size, bold=True):
    from PIL import ImageFont
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
              "/Library/Fonts", "C:/Windows/Fonts"):
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                        # Pillow < 10.1 has no sized default
        return ImageFont.load_default()


def render(results, path, ros_pts=None):
    from PIL import Image, ImageDraw

    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#00205B")
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, 14, H], fill="#FFFFFF")

    odds = results["odds"]["playoff"] * 100
    rec = results["record"]
    gl = results["games_left"]
    stamp = results["as_of"]
    name = f"{results.get('focus_city', 'Toronto')} {results.get('focus_name', 'Maple Leafs')}"

    dr.text((60, 48), f"{name.upper()} · PLAYOFF TRACKER", font=_font(30), fill="#FFFFFF")
    dr.text((60, 130), f"{odds:.1f}%", font=_font(190), fill="#FFFFFF")
    dr.text((66, 340), "chance of a playoff spot", font=_font(34, bold=False), fill="#C9D6EA")
    if results.get("preseason"):
        line = f"{gl} games to play"
    else:
        line = f"{rec['w']}–{rec['l']}–{rec['otl']}  ·  {rec['pts']} pts  ·  {gl} games left"
    if ros_pts is not None and gl:
        line += f"  ·  needs about {ros_pts} pts"
    size = 40
    while size > 24 and dr.textlength(line, font=_font(size)) > W - 120:
        size -= 2
    dr.text((60, 430), line, font=_font(size), fill="#FFFFFF")
    lead = "Preseason, on last year's form" if results.get("preseason") else f"Standings through {stamp}"
    dr.text((60, 540), f"{lead}  ·  {results['nsim']:,} simulated seasons",
            font=_font(24, bold=False), fill="#9FB3D6")
    im.save(path, "PNG", optimize=True)
    return path


def main(out):
    r = json.load(open("results.json"))
    try:
        p = json.load(open("path.json"))
        ros_pts = p.get("ros_needed_pts")
    except Exception:
        ros_pts = None
    try:
        render(r, out, ros_pts)
        print(f"  share card: {out} ({os.path.getsize(out)/1024:.0f} KB)")
    except Exception as e:                   # never fatal: a page without a card beats no page
        print(f"  note: share card not generated ({e})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "og.png")
