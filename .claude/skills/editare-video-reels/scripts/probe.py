"""Arată detaliile unui clip (rezoluție, fps, HDR, sunet) sau extrage cadre de verificare.

  python3 probe.py clip.mov
  python3 probe.py --frames final.mp4 [--every 5] [--out cadre.jpg]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import probe, ffmpeg_bin, run

ap = argparse.ArgumentParser()
ap.add_argument("clip")
ap.add_argument("--frames", action="store_true", help="fă o planșă cu cadre din clip")
ap.add_argument("--every", type=float, default=5.0)
ap.add_argument("--out", default="cadre.jpg")
a = ap.parse_args()
info = probe(a.clip)
if not a.frames:
    print(json.dumps(info, indent=1))
    print(f"\nSursa: {info['w']}x{info['h']} @ {info['fps']:.3f} fps, "
          f"{'HDR ' + info['transfer'] if info['hdr'] else 'SDR'}, {info['vcodec']} {info['pix_fmt']}, {info['dur']:.1f}s")
    print("Ieșirea trebuie să aibă exact aceleași valori.")
else:
    n = max(1, int(info["dur"] / a.every))
    cols = min(8, n)
    rows = (n + cols - 1) // cols
    run([ffmpeg_bin(), "-v", "error", "-y", "-i", a.clip, "-vf",
         f"fps=1/{a.every},scale=240:-2,tile={cols}x{rows}", "-frames:v", "1", a.out])
    print("Planșa:", a.out)
