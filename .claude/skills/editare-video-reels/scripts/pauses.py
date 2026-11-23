"""Strânge pauzele: taie liniștea de la capetele fiecărei bucăți și scurtează pauzele lungi din interior.
Taie doar pe liniște, deci nu rupe cuvinte.

  python3 pauses.py clip.mov edl.json edl_tight.json [--max 0.22] [--keep 0.07] [--thr -47]

edl.json: [{"i": start, "o": end}, ...] în secunde, în timpul sursei.
--thr: pragul de liniște în dBFS (măsoară cu --show dacă vocea e foarte încet).
Rezultatul e aliniat la cadre (fps-ul sursei).
"""
import argparse, json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common import ffmpeg_bin, probe

ap = argparse.ArgumentParser()
ap.add_argument("clip"); ap.add_argument("edl"); ap.add_argument("out")
ap.add_argument("--max", type=float, default=0.22, help="pauzele mai lungi de atât se scurtează")
ap.add_argument("--keep", type=float, default=0.07, help="liniște păstrată de fiecare parte a unei tăieturi")
ap.add_argument("--thr", type=float, default=-47)
ap.add_argument("--show", action="store_true", help="arată nivelul zgomotului de fond și al vocii")
a = ap.parse_args()
info = probe(a.clip); F = info["fps"]
raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", a.clip, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
hop = 160
db = np.array([20 * np.log10(np.sqrt(np.mean(x[i:i + hop] ** 2)) + 1e-9) for i in range(0, len(x) - hop, hop)])
if a.show:
    print("zgomot de fond (p10): %.1f dB, voce (p90): %.1f dB" % tuple(np.percentile(db, [10, 90])))
E = json.load(open(a.edl))
out = []
for s in E:
    i, o = s["i"], s["o"]
    k0, k1 = int(i * 100), int(o * 100)
    act = np.where(db[k0:k1] > a.thr)[0]
    if len(act):
        i = max(i, i + act[0] / 100 - 0.04)
        o = min(o, s["i"] + (act[-1] + 1) / 100 + 0.06)
    k0, k1 = int(i * 100), int(o * 100)
    sil = db[k0:k1] < a.thr
    regs, st = [], None
    for j, v in enumerate(sil):
        if v and st is None: st = j
        if not v and st is not None: regs.append((st, j)); st = None
    cur = i
    for r0, r1 in regs:
        ra, rb = i + r0 / 100, i + r1 / 100
        if ra <= i + 0.02 or rb >= o - 0.02 or rb - ra <= a.max:
            continue
        ca, cb = ra + a.keep, rb - a.keep
        n = round((ca - cur) * F)
        if n > 0:
            out.append(dict(i=round(cur, 4), n=n))
        cur = round(cur + n / F + round((cb - (cur + n / F)) * F) / F, 4)
    n = round((o - cur) * F)
    if n > 0:
        out.append(dict(i=round(cur, 4), n=n))
T = 0
for s in out:
    s["o"] = round(s["i"] + s["n"] / F, 4); s["T0"] = round(T, 4); T += s["n"] / F
json.dump(out, open(a.out, "w"), indent=0)
print(f"{len(E)} bucăți -> {len(out)} după strângerea pauzelor; durată finală {T:.2f}s")
