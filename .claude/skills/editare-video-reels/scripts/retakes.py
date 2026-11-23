"""Găsește reluările: fraze care încep cu aceleași 3+ cuvinte de mai multe ori.
Regula: păstrează ULTIMA variantă completă; variantele de dinainte sunt, de obicei, greșeli.

  python3 retakes.py words.json [--n 3] [--window 60]

Afișează și transcrierea împărțită pe fraze (după pauze), cu timpi, ca să construiești edl.json.
"""
import argparse, json, re

ap = argparse.ArgumentParser()
ap.add_argument("words")
ap.add_argument("--n", type=int, default=3, help="câte cuvinte la rând trebuie să se repete")
ap.add_argument("--window", type=float, default=60, help="secunde în care caut repetiția")
ap.add_argument("--gap", type=float, default=0.45, help="pauza (s) care desparte frazele")
a = ap.parse_args()
w = json.load(open(a.words))
norm = lambda t: re.sub(r"[^\wăâîșțşţ]", "", t.lower())

# phrases split on pauses / sentence punctuation
phr, cur = [], []
for i, x in enumerate(w):
    if cur and (x["s"] - cur[-1]["e"] > a.gap or re.search(r"[.?!]$", cur[-1]["w"])):
        phr.append(cur); cur = []
    cur.append(x)
if cur:
    phr.append(cur)
print("=== Fraze ===")
for k, p in enumerate(phr):
    low = [q["w"] for q in p if q.get("p", 1) < 0.5]
    print(f"#{k:03d} [{p[0]['s']:7.2f}-{p[-1]['e']:7.2f}] {' '.join(q['w'] for q in p)}" + (f"   (nesigure: {', '.join(low)})" if low else ""))

print("\n=== Posibile reluări (păstrează ultima variantă) ===")
seen = {}
for k, p in enumerate(phr):
    toks = [norm(q["w"]) for q in p]
    if len(toks) < a.n:
        continue
    key = " ".join(toks[:a.n])
    for j in seen.get(key, []):
        if p[0]["s"] - phr[j][0]["s"] < a.window:
            print(f"#{j:03d} ({phr[j][0]['s']:.2f}s) și #{k:03d} ({p[0]['s']:.2f}s) încep la fel: \"{key}\"")
    seen.setdefault(key, []).append(k)
# immediate word repetitions (stutters)
for i in range(len(w) - 2):
    if norm(w[i]["w"]) and norm(w[i]["w"]) == norm(w[i + 1]["w"]) and len(norm(w[i]["w"])) > 2:
        print(f"Cuvânt dublat la {w[i]['s']:.2f}s: \"{w[i]['w']} {w[i+1]['w']}\"")
