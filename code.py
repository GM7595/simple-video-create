#!/usr/bin/env python3
import subprocess, pathlib, shutil, re, sys, tkinter as tk
from tkinter import filedialog
from tqdm import tqdm

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
MP4_COPY_OK = {"aac", "mp3", "alac"}          # codecs safe to copy

EVEN_FILTER = "scale='trunc(iw/2)*2:trunc(ih/2)*2'"        # fixes odd W/H :contentReference[oaicite:0]{index=0}
# EVEN_FILTER = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1"


# ─────────────────── Finder picker ────────────────────
def choose():
    root = tk.Tk(); root.withdraw()
    paths = filedialog.askopenfilenames(
        title="Pick ONE audio + ONE image",
        filetypes=[("Audio & Image", " ".join(f"*{e}" for e in AUDIO_EXTS | IMAGE_EXTS))]
    )
    root.destroy()
    if len(paths) != 2:
        sys.exit("❌  Select exactly one audio and one image.")
    audio = image = None
    for p in paths:
        ext = pathlib.Path(p).suffix.lower()
        if ext in AUDIO_EXTS:  audio = p
        elif ext in IMAGE_EXTS: image = p
    if not (audio and image):
        sys.exit("❌  Couldn’t detect both an audio *and* an image.")
    return audio, image

# ────────────────── ffprobe helpers ───────────────────
def probe(*args):
    return subprocess.check_output(args, text=True).strip()

def duration(path):
    return float(probe("ffprobe","-v","quiet",
                       "-show_entries","format=duration",
                       "-of","default=noprint_wrappers=1:nokey=1", path))

def audio_codec(path):
    return probe("ffprobe","-v","quiet","-select_streams","a:0",
                 "-show_entries","stream=codec_name","-of","csv=p=0", path)

# ──────────────────── main muxer ──────────────────────
def mux(audio, image):
    reencode = audio_codec(audio).lower() not in MP4_COPY_OK  # PCM?  → AAC
    out      = pathlib.Path(audio).with_suffix(".mp4")
    dur      = duration(audio)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image,
        "-i", audio,
        "-vf", EVEN_FILTER,
        "-c:v", "libx264", "-tune", "stillimage",
        "-pix_fmt", "yuv420p",                       # web-safe video  :contentReference[oaicite:1]{index=1}
    ]
    cmd += ["-c:a", "aac", "-b:a", "192k"] if reencode else ["-c:a", "copy"]
    cmd += ["-shortest", "-progress", "pipe:1", "-nostats", str(out)]

    print("⇢", " ".join(cmd))                       # human-readable cmd

    with subprocess.Popen(cmd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          bufsize=1) as proc, \
         tqdm(total=dur, unit="s",
              bar_format="{l_bar}{bar}| {n:.0f}/{total:.0f}s") as bar:
        last = 0.0
        for line in proc.stdout:
            m = re.search(r"out_time_ms=(\d+)", line)
            if m:
                now = int(m.group(1)) / 1_000_000
                bar.update(now - last)
                last = now
        if proc.wait():
            print("\nFFmpeg log (tail):\n", line)
            sys.exit("❌  FFmpeg failed.")
    print("✅  Saved", out)

if __name__ == "__main__":
    audio, image = choose()
    mux(audio, image)
