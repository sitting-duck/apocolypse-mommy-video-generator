#!/usr/bin/env python3
# make_video.py — 30s daily survival short generator (Pexels + TTS + MoviePy)

import os, re, io, math, random, shutil, datetime, tempfile, asyncio, json, textwrap, subprocess, sys
from pathlib import Path
from typing import List, Tuple

import requests
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip

# =========================
# Config
# =========================
TARGET_SECONDS = 30
MIN_CLIP = 5
MAX_CLIP = 12
MAX_DOWNLOADS = 6

RANDOM_TOPICS = [
    "72-hour blackout checklist", "wildfire evacuation plan",
    "winter storm essentials", "go-bag for two adults",
    "water storage basics", "NOAA radio—why it matters",
    "first-aid for cuts and bleeding", "safe lighting during outages",
    "phone power when the grid is down", "storm prep 24 hours out"
]

# =========================
# Utilities
# =========================
def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def seconds_of_audio(mp3_path: Path) -> float:
    with AudioFileClip(str(mp3_path)) as a:
        return float(a.duration or 0.0)

# =========================
# Script generation (Ollama or fallback)
# =========================
def script_from_template(topic: str) -> str:
    return (f"Today’s survival tip: {topic}. Store at least one gallon of water per person per day, "
            f"keep shelf-stable food and a manual can opener, and use battery lanterns for safe indoor light. "
            f"Carry a NOAA weather radio and a charged power bank for phones. "
            f"Pack a basic first-aid kit with a trauma bandage and gloves. "
            f"Simple steps now make stressful situations safer and easier.")

def gen_script_ollama(topic: str, ollama_url: str, model: str) -> str:
    prompt = (
        "Write a 30-second, ~65–85 word script in a calm, practical tone for a survival/preparedness short.\n"
        f"Topic: {topic}\n"
        "Requirements:\n"
        "- Direct, prescriptive tips\n"
        "- No fear-mongering\n"
        "- End with a one-sentence takeaway\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write concise 30-second scripts for survival tips."},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.5, "num_predict": 200}
    }
    r = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    text = data.get("message", {}).get("content", "").strip()
    return text or script_from_template(topic)

# =========================
# TTS with Edge-TTS + macOS 'say' fallback  (YOUR BLOCK, kept intact)
# =========================
# ---------- TTS with Edge-TTS + macOS 'say' fallback ----------
import tempfile, textwrap, asyncio
from pathlib import Path

async def _tts_edge_async(text: str, voice: str, out_mp3: Path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate="+0%")
    await communicate.save(str(out_mp3))

def _tts_say(text: str, voice_hint: str, out_mp3: Path):
    """
    macOS fallback using 'say'. Renders AIFF then converts to MP3 via ffmpeg.
    """
    aiff = out_mp3.with_suffix(".aiff")
    # rough voice mapping; change as you like
    mac_voice = {
        "en-US-JennyNeural": "Samantha",
        "en-US-GuyNeural": "Alex",
    }.get(voice_hint, "Samantha")

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
        tf.write(textwrap.fill(text, 120))
        tmp_path = tf.name

    try:
        subprocess.run(["say", "-v", mac_voice, "-r", "185", "-f", tmp_path, "-o", str(aiff)], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff), str(out_mp3)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        try: os.remove(tmp_path)
        except Exception: pass
        try: aiff.unlink()
        except Exception: pass

def gen_tts(text: str, voice: str, out_mp3: Path):
    """
    Select backend via env TTS_BACKEND=edge|say (default=edge with fallback to 'say' on macOS).
    """
    backend = os.getenv("TTS_BACKEND", "edge").lower()
    if backend == "say":
        if sys.platform != "darwin":
            raise RuntimeError("TTS_BACKEND=say only works on macOS.")
        _tts_say(text, voice, out_mp3)
        return

    # Try Edge-TTS first
    try:
        import edge_tts  # import check
        asyncio.run(_tts_edge_async(text, voice, out_mp3))
    except Exception as e:
        if sys.platform == "darwin":
            print(f"[TTS] Edge-TTS failed ({e}); falling back to macOS 'say'…")
            _tts_say(text, voice, out_mp3)
        else:
            raise

# =========================
# Pexels search & download
# =========================
def pexels_search_videos(api_key: str, query: str, per_page: int = 15) -> List[dict]:
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": per_page}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("videos", [])

def choose_video_files(video_item: dict) -> List[Tuple[str, int]]:
    files = video_item.get("video_files", [])
    out = []
    for f in files:
        if f.get("file_type") == "video/mp4":
            out.append((f.get("link"), int(f.get("height") or 0)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out

def download_binary(url: str, dest: Path):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f)

def fetch_stock_clips(api_key: str, query: str, tmpdir: Path) -> List[Path]:
    vids = pexels_search_videos(api_key, query)
    paths: List[Path] = []
    random.shuffle(vids)
    for v in vids:
        files = choose_video_files(v)
        if not files:
            continue
        pick = files[min(1, len(files)-1)]  # prefer mid/high quality
        url = pick[0]
        name = f"pexels_{v.get('id')}.mp4"
        dest = tmpdir / name
        try:
            download_binary(url, dest)
            paths.append(dest)
            if len(paths) >= MAX_DOWNLOADS:
                break
        except Exception:
            continue
    return paths

# =========================
# Captions (simple SRT)
# =========================
def make_srt(text: str, total_seconds: float) -> str:
    chunks = [c.strip() for c in re.split(r'(?<=[.!?])\s+', text) if c.strip()]
    if not chunks:
        chunks = [text.strip()]
    per = total_seconds / len(chunks)
    def fmt(t: float):
        h = int(t // 3600); t -= h*3600
        m = int(t // 60); t -= m*60
        s = int(t); ms = int((t - s) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    out = []
    cur = 0.0
    for i, c in enumerate(chunks, 1):
        start = cur; end = min(total_seconds, cur + per)
        out.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{c}\n")
        cur = end
    return "\n".join(out)

# =========================
# Build final video
# =========================
def build_video(clips: List[Path], voice_mp3: Path, out_path: Path):
    audio = AudioFileClip(str(voice_mp3))
    vclips = []
    total = 0.0
    for p in clips:
        try:
            vc = VideoFileClip(str(p))
            dur = float(vc.duration or 0.0)
            seg = min(MAX_CLIP, max(MIN_CLIP, dur if dur < MAX_CLIP else MAX_CLIP))
            sub = vc.subclip(0, min(seg, dur)).without_audio()
            vclips.append(sub)
            total += sub.duration
            if total >= TARGET_SECONDS:
                break
        except Exception:
            continue
    if not vclips:
        raise RuntimeError("No usable clips downloaded.")
    video = concatenate_videoclips(vclips, method="compose").set_duration(TARGET_SECONDS)
    final = video.set_audio(audio)
    final.write_videofile(str(out_path), codec="libx264", audio_codec="aac", fps=30, bitrate="3500k")
    # cleanup
    for vc in vclips:
        vc.close()
    audio.close()
    video.close()

# =========================
# Orchestrator
# =========================
def main():
    print("[make_video] starting…")
    load_dotenv()
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    if not pexels_key:
        raise SystemExit("Missing PEXELS_API_KEY (set in ~/.zshrc or .env)")

    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5")
    voice = os.getenv("VOX", "en-US-JennyNeural")

    topic = random.choice(RANDOM_TOPICS)
    date = datetime.date.today().isoformat()
    outdir = Path("daily_videos"); ensure_dir(outdir)
    work = Path(tempfile.mkdtemp(prefix="dailyvid_"))

    try:
        # 1) Script
        try:
            script = gen_script_ollama(topic, ollama_url, model)
        except Exception as e:
            print(f"[script] Ollama failed ({e}); using template.")
            script = script_from_template(topic)
        (work / f"script_{date}.txt").write_text(script, encoding="utf-8")

        # 2) TTS
        voice_mp3 = work / f"voice_{date}.mp3"
        gen_tts(script, voice, voice_mp3)
        _ = seconds_of_audio(voice_mp3)  # duration not strictly needed

        # 3) Download stock videos
        query = topic.split(":")[0].split("—")[0]
        clips = fetch_stock_clips(pexels_key, query, work)
        if not clips:
            clips = fetch_stock_clips(pexels_key, "survival emergency preparedness", work)
        if not clips:
            raise RuntimeError("No clips found from Pexels API.")

        # 4) Build video
        out_mp4 = outdir / f"daily_video_{slugify(topic)}_{date}.mp4"
        build_video(clips, voice_mp3, out_mp4)

        # 5) Captions
        srt = make_srt(script, TARGET_SECONDS)
        (outdir / f"daily_video_{slugify(topic)}_{date}.srt").write_text(srt, encoding="utf-8")

        print(f"✅ Generated: {out_mp4}")

    finally:
        shutil.rmtree(work, ignore_errors=True)

# Entry point
if __name__ == "__main__":
    main()
