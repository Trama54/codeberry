"""Shared helpers: locate ffmpeg/ffprobe, probe media, pick encoder settings that match the source."""
import json, os, re, shutil, subprocess, sys


def ffmpeg_bin():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg nu e instalat. Rulează: pip install imageio-ffmpeg")


def ffprobe_bin():
    return shutil.which("ffprobe")


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit(f"Comanda a eșuat: {' '.join(args[:6])} ...")
    return r


def probe(path):
    """Return dict: w, h, fps (float), fps_str, dur, vcodec, pix_fmt, transfer, primaries, matrix, hdr, achannels, arate."""
    fp = ffprobe_bin()
    info = {}
    if fp:
        r = run([fp, "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
        j = json.loads(r.stdout)
        v = next(s for s in j["streams"] if s["codec_type"] == "video")
        a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
        num, den = v.get("r_frame_rate", "30/1").split("/")
        info.update(
            w=int(v["width"]), h=int(v["height"]), fps=float(num) / float(den), fps_str=v.get("r_frame_rate"),
            dur=float(j["format"].get("duration", 0)), vcodec=v["codec_name"], pix_fmt=v.get("pix_fmt", "yuv420p"),
            transfer=v.get("color_transfer", "bt709"), primaries=v.get("color_primaries", "bt709"),
            matrix=v.get("color_space", "bt709"), achannels=int(a["channels"]) if a else 0,
            arate=int(a["sample_rate"]) if a else 48000,
        )
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        info["rotation"] = rot
    else:  # parse ffmpeg -i
        r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", path], capture_output=True, text=True)
        s = r.stderr
        m = re.search(r"Video: (\w+).*?, (\w+)\(([^)]*)\).*?, (\d+)x(\d+).*?, ([\d.]+) fps", s)
        d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", s)
        info.update(vcodec=m.group(1), pix_fmt=m.group(2), w=int(m.group(4)), h=int(m.group(5)), fps=float(m.group(6)),
                    fps_str=m.group(6), dur=int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)),
                    transfer="arib-std-b67" if "arib" in s else ("smpte2084" if "smpte2084" in s else "bt709"),
                    primaries="bt2020" if "bt2020" in s else "bt709", matrix="bt2020nc" if "bt2020" in s else "bt709",
                    achannels=2, arate=48000, rotation=0)
    info["hdr"] = info["transfer"] in ("arib-std-b67", "smpte2084")
    info["ten_bit"] = "10" in info["pix_fmt"] or info["hdr"]
    return info


def encoder_args(info, crf=None, preset="medium"):
    """Encoder flags that keep the source look: same codec family, bit depth and colour tags."""
    tags = ["-color_primaries", info["primaries"], "-color_trc", info["transfer"], "-colorspace", info["matrix"]]
    if info["hdr"] or info["vcodec"] == "hevc":
        x265p = (f"colorprim={info['primaries']}:transfer={info['transfer']}:colormatrix={info['matrix']}:"
                 "range=limited:repeat-headers=1:log-level=error")
        return ["-c:v", "libx265", "-preset", preset, "-crf", str(crf or 16),
                "-pix_fmt", "yuv420p10le" if info["ten_bit"] else "yuv420p",
                "-x265-params", x265p, "-tag:v", "hvc1"] + tags
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf or 14), "-pix_fmt", "yuv420p",
            "-profile:v", "high"] + tags


if __name__ == "__main__":
    print(json.dumps(probe(sys.argv[1]), indent=1))
