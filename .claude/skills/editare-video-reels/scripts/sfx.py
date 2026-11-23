"""Generează efecte sonore simple, fără drepturi de autor (WAV 48 kHz stereo).

  python3 sfx.py click click.wav      # click moale, ca un tap pe buton
  python3 sfx.py pop pop.wav          # pop scurt pentru un element care apare
  python3 sfx.py whoosh whoosh.wav    # tranziție
"""
import sys, wave
import numpy as np

SR = 48000


def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def click():
    n = int(0.09 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 1850 * t) * env(n, 0.0008, 0.010)
    thump = np.sin(2 * np.pi * 180 * t) * env(n, 0.001, 0.018) * 0.6
    tick = np.random.default_rng(1).normal(0, 1, n) * env(n, 0.0002, 0.0025) * 0.35
    return (body * 0.5 + thump + tick) * 0.45


def pop():
    n = int(0.12 * SR); t = np.arange(n) / SR
    f = 380 + 900 * np.exp(-t / 0.02)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.03) * 0.5


def whoosh():
    n = int(0.45 * SR); t = np.arange(n) / SR
    noise = np.random.default_rng(2).normal(0, 1, n)
    k = np.exp(-((t - 0.22) / 0.11) ** 2)
    # crude band-pass sweep via moving average of different lengths
    out = np.convolve(noise, np.ones(24) / 24, mode="same") - np.convolve(noise, np.ones(4) / 4, mode="same") * 0.3
    return out * k * 0.6


def save(x, path):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], 1)
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()


kind, path = sys.argv[1], sys.argv[2]
save({"click": click, "pop": pop, "whoosh": whoosh}[kind](), path)
print("scris", path)
