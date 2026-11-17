"""Mix narration (Microsoft Zira TTS) + ambient bed + UI click sounds, then encode MP4 with ffmpeg (imageio-ffmpeg).
Usage: python tools/demo/assemble.py"""
import json, math, os, re, subprocess, sys, wave
import numpy as np
import imageio_ffmpeg

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.argv = [sys.argv[0]]
# reuse timing from record.py without running it
src = open(os.path.join(ROOT, "tools", "demo", "record.py"), encoding="utf-8").read().split("# ---- camera presets")[0]
ns = {"__file__": os.path.join(ROOT, "tools", "demo", "record.py")}
exec(src.replace("import websockets", ""), ns)
LS, LE, TOTAL, FPS, SEG0 = ns["LS"], ns["LE"], ns["TOTAL"], ns["FPS"], ns["SEG0"]
src2 = open(os.path.join(ROOT, "tools", "demo", "record.py"), encoding="utf-8").read()
ACT_TIMES = [float(x) for x in re.findall(r"\(LS\[\((\d), (\d)\)\] \+ ([\d.]+), \"click\"", src2) and []]
exec("ACT=" + src2.split("ACT = ")[1].split("ACT.sort()")[0], {"LS": LS, "ACT": None}, ns)
click_times = sorted(t for t, k, _ in ns["ACT"] if k == "click")

SR = 44100
n = int((TOTAL + 0.5) * SR)
mix = np.zeros(n, dtype=np.float64)

def read(path):
    w = wave.open(path); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    assert w.getframerate() == SR; return a

# narration
voice = np.zeros(n)
for (seg, i), t in LS.items():
    a = read(os.path.join(ROOT, "tools", "out", "tts", f"s{seg}_{i}.wav"))
    s = int(t * SR); voice[s:s + len(a)] += a
voice *= 0.95

# ambient bed: soft evolving pad (original, synthesized)
t = np.arange(n) / SR
pad = (np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 82.4 * t + 0.6 * np.sin(2 * np.pi * 0.07 * t)) * 0.35
       + np.sin(2 * np.pi * 110 * t) * 0.25 + np.sin(2 * np.pi * 164.8 * t) * 0.12 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t)))
pad *= 0.045 * (0.75 + 0.25 * np.sin(2 * np.pi * 0.05 * t))
# gentle pulse (heartbeat of the alarm) while incident is open: every 1.6 s until recovery, then calm
rec_t = [tt for tt, k, tg in ns["ACT"] if "restore" in tg][0]
pulse = np.zeros(n)
tt = 0.0
while tt < rec_t:
    s = int(tt * SR); L = int(0.25 * SR); env = np.exp(-np.arange(L) / (0.05 * SR))
    pulse[s:s + L] += np.sin(2 * np.pi * 70 * np.arange(L) / SR) * env * 0.05
    tt += 1.6
# success chord at recovery
chord = np.zeros(n); s = int((rec_t + 0.3) * SR); L = int(2.2 * SR); env = np.exp(-np.arange(L) / (0.9 * SR)) * np.minimum(1, np.arange(L) / (0.02 * SR))
for f in (523.25, 659.25, 783.99):
    chord[s:s + L] += np.sin(2 * np.pi * f * np.arange(L) / SR) * env * 0.05
# UI click blips
clicks = np.zeros(n)
for ct in click_times:
    s = int(ct * SR); L = int(0.09 * SR); k = np.arange(L)
    clicks[s:s + L] += np.sin(2 * np.pi * 1320 * k / SR) * np.exp(-k / (0.02 * SR)) * 0.12
# title whoosh
w = np.zeros(n); L = int(1.6 * SR); k = np.arange(L); rng = np.random.default_rng(1)
w[:L] = rng.standard_normal(L) * np.sin(np.pi * k / L) ** 2 * 0.03
# duck the bed under voice
vo_env = np.convolve(np.abs(voice), np.ones(2205) / 2205, mode="same"); duck = 1 - 0.5 * np.clip(vo_env * 12, 0, 1)
bed = pad * duck + pulse * duck
fade = np.minimum(1, np.minimum(t / 1.5, np.maximum(0, (TOTAL + 0.3 - t)) / 1.5))
out = (voice + bed + chord + clicks + w) * fade
out = out / max(1.0, np.max(np.abs(out)) / 0.95)
wav_path = os.path.join(ROOT, "tools", "out", "mix.wav")
with wave.open(wav_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes((out * 32767).astype(np.int16).tobytes())

ff = imageio_ffmpeg.get_ffmpeg_exe()
dest = os.path.join(ROOT, "Submission", "demo", "Trustfall_demo.mp4")
cmd = [ff, "-y", "-framerate", str(FPS), "-i", os.path.join(ROOT, "tools", "out", "frames", "%05d.jpg"), "-i", wav_path,
       "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
       "-shortest", "-movflags", "+faststart", dest]
print(" ".join(cmd)); subprocess.run(cmd, check=True)
print("wrote", dest, "audio seconds", round(n / SR, 1), "narration speech ends", round(max(LE.values()), 1))
