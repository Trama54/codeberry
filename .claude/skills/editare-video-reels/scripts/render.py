"""Randează montajul final: tăieturi din EDL, zoom alternativ, poze/clipuri B-roll cu tranziții, subtitrări, efecte sonore.
Păstrează rezoluția, fps-ul, codecul și culoarea sursei. Sunetul iese stereo (vocea pe ambele canale), -16 LUFS.

  python3 render.py clip.mov edl.json final.mp4 [--captions words.json] [--caption-style clasic|minimal|bold]
                    [--accent "#FFD60A"] [--font font.ttf] [--caption-y 0.75] [--hide-captions 2.3-3.9,...]
                    [--zoom-alternate] [--edits edits.json]
  python3 render.py clip.mov edl.json voce.m4a --audio-only

edl.json  : [{"i": start, "o": end}, ...] în timpul sursei (ieșirea lui pauses.py e perfectă).
words.json: cuvintele din transcribe.py (timpul sursei). Cuvintele din bucățile tăiate dispar singure.
edits.json: elemente puse peste montaj, în timpul FINAL (secunde din clipul editat):
  [
    {"type": "image", "path": "poza.jpg", "start": 3.0, "end": 5.5, "in": "zoom", "out": "fade", "kenburns": true},
    {"type": "video", "path": "broll.mp4", "start": 8.0, "end": 11.0, "offset": 1.2, "in": "slide", "out": "fade"},
    {"type": "image", "path": "logo.png", "start": 0, "end": 4, "x": 0.5, "y": 0.2, "w": 0.6, "in": "pop", "out": "fade"},
    {"type": "flash", "at": 14.0, "dur": 0.18},
    {"type": "sfx", "path": "whoosh.wav", "at": 7.8, "gain": 0.6}
  ]
  "in"/"out": none | fade | slide (din dreapta) | slideup (de jos) | zoom (pe tot ecranul) | pop (elemente mici)
  "dur": durata tranziției (implicit 0.25 s). "kenburns": zoom lent pe poză, ca să nu stea înghețată.
  "offset": de unde începe clipul B-roll. Elementele mici (cu "w") sunt PNG-uri, se pot pune cu transparență.
"""
import argparse, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from common import ffmpeg_bin, probe, encoder_args

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

STYLES = {
    # alb cu contur negru, cuvântul rostit colorat
    "clasic": dict(font="Inter-ExtraBold.otf", size=0.080, upper=False, accent="#FFD60A", stroke=True, box=False, maxw=3),
    # discret: alb cu umbră, fără evidențiere, mai mic
    "minimal": dict(font="Inter-Bold.otf", size=0.062, upper=False, accent=None, stroke=False, box=False, maxw=4),
    # majuscule, cuvântul rostit pe o etichetă colorată
    "bold": dict(font="Inter-Black.otf", size=0.078, upper=True, accent="#22C55E", stroke=True, box=True, maxw=3),
}


def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def build_caption_track(words, segs, W, H, total, hdr, tmpdir, style, hide=(), ypos=0.75):
    """Map words to output time, group them, render one PNG per (group, active word) and write an ffconcat list."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    out = []
    for x in words:
        for s in segs:
            if s["i"] - 0.02 <= x["s"] < s["o"]:
                t0 = s["T0"] + (x["s"] - s["i"]); t1 = s["T0"] + (min(x["e"], s["o"]) - s["i"])
                out.append(dict(w=x["w"], s=max(0, t0), e=max(t0 + 0.05, t1))); break
    # cuvintele scrise deja pe ecran nu se mai subtitrează; grupul se rupe în jurul golului
    kept = []
    for x in out:
        if any(a <= x["s"] < b for a, b in hide):
            if kept: kept[-1]["brk"] = True
            continue
        kept.append(x)
    m = []
    for x in kept:  # lipește „-ul”, „-ți” de cuvântul dinainte
        if m and x["w"].startswith("-"):
            m[-1]["w"] += x["w"]; m[-1]["e"] = x["e"]
        else:
            m.append(dict(x))
    groups, cur = [], []
    for x in m:
        txt = " ".join(c["w"] for c in cur + [x])
        if cur and (cur[-1].get("brk") or len(cur) >= style["maxw"] or len(txt) > 18 or x["s"] - cur[-1]["e"] > 0.35
                    or re.search(r"[.?!,]$", cur[-1]["w"])):
            groups.append(cur); cur = []
        cur.append(x)
    if cur: groups.append(cur)
    fs = int(W * style["size"])
    font = ImageFont.truetype(style["font"], fs)
    k = 0.75 if hdr else 1.0  # în HDR (HLG) albul de referință stă la ~75%
    white = tuple(int(c * k) for c in (245, 245, 245))
    acc = tuple(int(c * k) for c in hex2rgb(style["accent"])) if style["accent"] else white
    y = int(H * ypos)
    blank = os.path.join(tmpdir, "blank.png"); Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    entries, t, idx = [], 0.0, 0
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else total
        for j, x in enumerate(g):
            s = x["s"]; e = g[j + 1]["s"] if j + 1 < len(g) else min(x["e"] + 0.25, nxt)
            if s > t: entries.append((blank, s - t)); t = s
            if e <= t: continue
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            ws = [c["w"].rstrip(",.?!…:;") for c in g]
            if style["upper"]: ws = [w_.upper() for w_ in ws]
            widths = [d.textlength(w_, font=font) for w_ in ws]
            sp = fs * 0.28; tw = sum(widths) + sp * (len(ws) - 1); xx = (W - tw) / 2
            if not style["stroke"]:  # umbră moale
                sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh); x2 = xx
                for n, w_ in enumerate(ws):
                    sd.text((x2, y + fs * 0.05), w_, font=font, fill=(0, 0, 0, 170), anchor="ls"); x2 += widths[n] + sp
                im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(fs * 0.08))); d = ImageDraw.Draw(im)
            for n, w_ in enumerate(ws):
                active = n == j and style["accent"]
                if active and style["box"]:
                    pad = fs * 0.16; top = y - fs * 0.80; bot = y + fs * 0.14
                    d.rounded_rectangle((xx - pad, top, xx + widths[n] + pad, bot), radius=fs * 0.18, fill=acc + (255,))
                fill = white if (style["box"] or not active) else acc
                kw = dict(stroke_width=max(4, fs // 14), stroke_fill=(0, 0, 0)) if style["stroke"] and not (active and style["box"]) else {}
                d.text((xx, y), w_, font=font, fill=fill, anchor="ls", **kw)
                xx += widths[n] + sp
            p = os.path.join(tmpdir, f"c{idx:05d}.png"); im.save(p); idx += 1
            entries.append((p, e - t)); t = e
    if total > t: entries.append((blank, total - t))
    lst = os.path.join(tmpdir, "caps.txt")
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for p, d_ in entries:
            f.write(f"file '{p}'\nduration {d_:.4f}\n")
        f.write(f"file '{entries[-1][0]}'\n")
    return lst


ap = argparse.ArgumentParser()
ap.add_argument("clip"); ap.add_argument("edl"); ap.add_argument("out")
ap.add_argument("--captions"); ap.add_argument("--edits")
ap.add_argument("--caption-style", default="clasic", choices=list(STYLES))
ap.add_argument("--accent", help="culoarea cuvântului rostit, ex. #FFD60A (alege-o după brandul utilizatorului)")
ap.add_argument("--font", help="alt font .ttf/.otf (implicit Inter, inclus în assets/)")
ap.add_argument("--caption-y", type=float, default=0.75, help="poziția subtitrării, 0-1 din înălțime (0.75 = sub gură)")
ap.add_argument("--hide-captions", default="", help="intervale în timpul FINAL fără subtitrare, ex: 2.3-3.9,13.6-14.6")
ap.add_argument("--zoom-alternate", action="store_true")
ap.add_argument("--zoom", type=float, default=1.15)
ap.add_argument("--audio-only", action="store_true")
ap.add_argument("--crf", type=int); ap.add_argument("--preset", default="medium")
ap.add_argument("--no-loudnorm", action="store_true")
a = ap.parse_args()

info = probe(a.clip); F = info["fps"]; W, H = info["w"], info["h"]
if info.get("rotation") in (90, -90, 270, -270): W, H = H, W
segs = json.load(open(a.edl)); T = 0
for s in segs:
    s["n"] = s.get("n") or round((s["o"] - s["i"]) * F); s["o"] = s["i"] + s["n"] / F; s["T0"] = T; T += s["n"] / F
total = T
tmp = tempfile.mkdtemp()
FF = ffmpeg_bin()
# ---------- sunet: tăieturi, micro-fade-uri, mono -> stereo, nivel, efecte
fc, al = [], []
for k, s in enumerate(segs):
    d = s["n"] / F
    fc.append(f"[0:a]atrim=start={s['i']:.4f}:end={s['o']:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
              f"afade=t=in:d=0.008,afade=t=out:st={max(0, d - 0.01):.4f}:d=0.01[a{k}]"); al.append(f"[a{k}]")
fc.append("".join(al) + f"concat=n={len(al)}:v=0:a=1,pan=mono|c0=c0,highpass=f=80" +
          ("" if a.no_loudnorm else ",loudnorm=I=-16:TP=-1.5:LRA=11") + ",pan=stereo|c0=c0|c1=c0[av]")
edits = json.load(open(a.edits)) if a.edits else []
sfx = [e for e in edits if e["type"] == "sfx"]
ain = [FF, "-v", "error", "-y", "-vn", "-i", a.clip]
last_a = "[av]"
if sfx:
    mix = [last_a]
    for n, e in enumerate(sfx, start=1):
        ain += ["-i", e["path"]]; ms = int(e["at"] * 1000)
        fc.append(f"[{n}:a]aresample=48000,volume={e.get('gain', 0.8)},adelay={ms}|{ms}[s{n}]"); mix.append(f"[s{n}]")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first[amx]"); last_a = "[amx]"
voice = a.out if a.audio_only else os.path.join(tmp, "voice.wav")
subprocess.run(ain + ["-filter_complex", ";".join(fc), "-map", last_a, "-t", f"{total:.4f}"] +
               (["-c:a", "aac", "-b:a", "192k"] if a.audio_only else ["-c:a", "pcm_s16le"]) + [voice], check=True)
if a.audio_only:
    print("Voce:", a.out, f"{total:.2f}s"); sys.exit()

# ---------- pasul 1: fiecare bucată separat (nu umple memoria la 4K60), apoi lipite fără re-encodare
fps = info["fps_str"] or str(F)
parts = []
for k, s in enumerate(segs):
    z = ""
    if a.zoom_alternate and k % 2 == 1:
        zw, zh = int(W * a.zoom) // 2 * 2, int(H * a.zoom) // 2 * 2
        z = f",scale={zw}:{zh}:flags=bicubic,crop={W}:{H}:{(zw - W) // 2}:{int((zh - H) * 0.35)}"
    p = os.path.join(tmp, f"part{k:03d}.mkv")
    subprocess.run([FF, "-v", "error", "-y", "-ss", f"{s['i']:.4f}", "-i", a.clip, "-t", f"{s['n'] / F:.4f}", "-an",
                    "-vf", f"fps={fps}{z},setsar=1", "-frames:v", str(s["n"])] + encoder_args(info, 8, "veryfast") + [p], check=True)
    parts.append(p); print(f"  bucata {k + 1}/{len(segs)}", flush=True)
lst = os.path.join(tmp, "parts.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
joined = os.path.join(tmp, "joined.mkv")
subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)

# ---------- pasul 2: poze/clipuri cu tranziții, flash-uri, subtitrări, encodare finală
# Grafica (sRGB) se convertește explicit în spațiul de culoare al sursei, altfel culorile ies decalate.
if info["hdr"]:
    TOYUV = (",setparams=color_primaries=bt709:color_trc=iec61966-2-1:colorspace=bt709,zscale=t=linear:npl=203,format=gbrpf32le,"
             f"zscale=p=bt2020:t={info['transfer']}:m=bt2020nc:r=tv:npl=203,format=yuv420p10le")
    ALPHA = "yuva420p10le"
else:
    TOYUV = ",scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
    ALPHA = "yuva420p"


def fades(e, length):
    """Fade-uri pe canalul alfa pentru intrare/ieșire."""
    d = e.get("dur", 0.25); f = ""
    if e.get("in", "fade") != "none": f += f",fade=t=in:st=0:d={min(d, 0.15) if e.get('in') == 'pop' else d}:alpha=1"
    if e.get("out", "fade") != "none": f += f",fade=t=out:st={max(0, length - d):.3f}:d={d}:alpha=1"
    return f


def ease(expr):  # ieșire lină (cubic) pentru o valoare 0..1
    return f"(1-pow(1-({expr}),3))"


inputs = [FF, "-v", "error", "-stats", "-y", "-i", joined, "-i", voice]
fc = []; last = "[0:v]"; nin = 2
vis = [e for e in edits if e["type"] in ("image", "video", "flash")]
for k, e in enumerate(vis):
    if e["type"] == "flash":  # flash alb scurt, ca tranziție între idei
        d = e.get("dur", 0.18); st = e["at"]
        inputs += ["-f", "lavfi", "-i", f"color=c=white:s={W}x{H}:r={F}:d={d + 0.05}"]
        fc.append(f"[{nin}:v]format=rgb24{TOYUV},format={ALPHA},fade=t=out:st=0:d={d}:alpha=1,setpts=PTS-STARTPTS+{st}/TB[o{k}]")
        fc.append(f"{last}[o{k}]overlay=0:0:eof_action=pass:enable='between(t,{st},{st + d})'[l{k}]")
        nin += 1; last = f"[l{k}]"; continue
    st, en = e["start"], e["end"]; L = en - st; d = e.get("dur", 0.25); N = max(1, round(L * F))
    if e["type"] == "image":
        inputs += ["-loop", "1", "-framerate", str(F), "-t", f"{L + 0.1:.3f}", "-i", e["path"]]
    else:
        inputs += ["-ss", str(e.get("offset", 0)), "-t", f"{L + 0.1:.3f}", "-i", e["path"]]
    src = f"[{nin}:v]"; nin += 1
    pin = ease(f"min(1,(t-{st})/{d})")
    if "w" in e:  # element mic (logo, captură, sticker) peste video; transparența PNG-ului se păstrează
        pw = int(W * e["w"]) // 2 * 2
        fc.append(f"{src}fps={F},scale={pw}:-2,format=rgba,split[k{k}a][k{k}b]")
        fc.append(f"[k{k}a]format=rgb24{TOYUV}[k{k}c];[k{k}b]alphaextract[k{k}d]")
        fc.append(f"[k{k}c][k{k}d]alphamerge,format={ALPHA}{fades(e, L)},setpts=PTS-STARTPTS+{st}/TB[o{k}]")
        cx, cy = int(W * e.get("x", .5)), int(H * e.get("y", .5))
        rise = {"slideup": 0.08, "pop": 0.02}.get(e.get("in"), 0)
        ypos = f"{cy}-h/2+{int(H * rise)}*(1-{pin})" if rise else f"{cy}-h/2"
        xpos = f"{cx}-w/2+{int(W * 0.6)}*(1-{pin})" if e.get("in") == "slide" else f"{cx}-w/2"
        fc.append(f"{last}[o{k}]overlay=x='{xpos}':y='{ypos}':eval=frame:eof_action=pass:enable='between(t,{st},{en})'[l{k}]")
    else:  # pe tot ecranul
        g = f"{src}fps={F},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
        kb = e.get("kenburns", e["type"] == "image")
        if kb or e.get("in") == "zoom":
            z = "1"
            if kb: z += f"*(1+0.08*on/{N})"  # zoom lent 100% -> 108%
            if e.get("in") == "zoom": z += f"*(1+0.15*(1-{ease(f'min(1,on/{d * F:.2f})')}))"  # intră de la 115%
            g += f",zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={F}"
        g += f"{TOYUV},format={ALPHA}" + fades(dict(e, **{"in": "fade" if e.get("in", "fade") in ("fade", "zoom") else "none"}), L)
        fc.append(g + f",setpts=PTS-STARTPTS+{st}/TB[o{k}]")
        xpos = f"{W}*(1-{pin})" if e.get("in") == "slide" else "0"
        ypos = f"{H}*(1-{pin})" if e.get("in") == "slideup" else "0"
        fc.append(f"{last}[o{k}]overlay=x='{xpos}':y='{ypos}':eval=frame:eof_action=pass:enable='between(t,{st},{en})'[l{k}]")
    last = f"[l{k}]"
if a.captions:
    style = dict(STYLES[a.caption_style])
    if a.accent: style["accent"] = a.accent
    style["font"] = a.font or os.path.join(ASSETS, style["font"])
    hide = [tuple(map(float, r.split("-"))) for r in a.hide_captions.split(",") if r]
    clst = build_caption_track(json.load(open(a.captions)), segs, W, H, total, info["hdr"], tmp, style, hide, a.caption_y)
    inputs += ["-f", "concat", "-safe", "0", "-i", clst]
    mat = "bt2020" if info["hdr"] else "bt709"
    fc.append(f"[{nin}:v]format=rgba,fps={F},scale=out_color_matrix={mat}:out_range=tv,format={ALPHA}[cap]"); nin += 1
    fc.append(f"{last}[cap]overlay=0:0:eof_action=pass:format=auto[vcap]"); last = "[vcap]"
if not fc:
    fc.append("[0:v]null[vout]"); last = "[vout]"
cmd = inputs + ["-filter_complex", ";".join(fc), "-map", last, "-map", "1:a", "-t", f"{total:.4f}"] + \
      encoder_args(info, a.crf, a.preset) + ["-r", fps, "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                                             "-movflags", "+faststart", a.out]
print("Randare finală", f"{W}x{H}@{F:.2f}", f"{total:.2f}s", "->", a.out, flush=True)
if os.environ.get("RENDER_DEBUG"): print(" ".join(cmd))
subprocess.run(cmd, check=True)
print("Gata:", a.out)
