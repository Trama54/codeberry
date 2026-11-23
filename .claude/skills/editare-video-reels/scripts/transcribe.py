"""Transcriere cu timpi pe cuvânt (faster-whisper) sau conversie dintr-un .srt.

  python3 transcribe.py clip.mov words.json --lang ro [--model large-v3] [--prompt "nume proprii, termeni"]
  python3 transcribe.py --srt subtitrari.srt words.json

Rezultat: listă JSON [{"w": cuvânt, "s": start, "e": final, "p": probabilitate}, ...]
Afișează și textul pe fraze, cu timpi, ca să-l citești ca un editor.
"""
import argparse, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from common import ffmpeg_bin


def from_srt(path):
    txt = open(path, encoding="utf-8-sig").read()
    words = []
    for blk in re.split(r"\n\s*\n", txt.strip()):
        lines = blk.strip().splitlines()
        m = next((re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", l) for l in lines if "-->" in l), None)
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(l for l in lines if "-->" not in l and not l.strip().isdigit())
        toks = text.split()
        for k, t in enumerate(toks):  # spread evenly inside the cue
            words.append(dict(w=t, s=round(s + (e - s) * k / len(toks), 3), e=round(s + (e - s) * (k + 1) / len(toks), 3), p=0.5))
    return words


def transcribe(clip, lang, model_name, prompt):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"], check=False)
        from faster_whisper import WhisperModel
    import numpy as np, wave
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", clip, "-vn", "-ac", "1", "-ar", "16000", tmp], check=True)
    wf = wave.open(tmp)
    audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    last = None
    for name in [model_name, "medium", "small"]:
        try:
            m = WhisperModel(name, device="cpu", compute_type="int8")
            break
        except Exception as ex:  # model download blocked -> try a smaller one
            last = ex
            m = None
    if m is None:
        sys.exit(f"Nu pot descărca modelul Whisper ({last}). Cere utilizatorului un .srt (CapCut: Subtitrări automate -> Export .srt) și rulează --srt.")
    segs, _ = m.transcribe(audio, language=lang, beam_size=5, word_timestamps=True,
                           condition_on_previous_text=False, initial_prompt=prompt or None)
    words = []
    for s in segs:
        print(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text.strip()}", flush=True)
        words += [dict(w=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3), p=round(w.probability, 2)) for w in s.words]
    return words


ap = argparse.ArgumentParser()
ap.add_argument("clip", nargs="?")
ap.add_argument("out")
ap.add_argument("--lang", default="ro")
ap.add_argument("--model", default="large-v3")
ap.add_argument("--prompt", default="")
ap.add_argument("--srt")
a = ap.parse_args()
words = from_srt(a.srt) if a.srt else transcribe(a.clip, a.lang, a.model, a.prompt)
json.dump(words, open(a.out, "w"), ensure_ascii=False, indent=0)
print(f"\n{len(words)} cuvinte -> {a.out}")
