# ---------- TTS with Edge-TTS + macOS 'say' fallback ----------
import sys, subprocess, tempfile, textwrap, asyncio
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

