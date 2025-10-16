# Daily Survival Video Generator

This project automatically generates a **30-second survival/preparedness video** every day.  
It uses your Ollama LLM to write a short script, downloads free stock footage from Pexels, generates a voiceover, stitches everything together with captions, and exports to MP4.

---

## Features
- Picks a random survival topic daily
- Generates a concise 30s narration script (via Ollama or fallback template)
- Creates natural-sounding voiceover with [Edge-TTS](https://github.com/rany2/edge-tts)
- Downloads **free stock video clips** from [Pexels API](https://www.pexels.com/api/)
- Combines clips to ~30s, overlays TTS audio, and exports `daily_video_YYYY-MM-DD.mp4`
- Auto-generates `.srt` captions from the script
- Designed for automation via cron

---

## Requirements
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) installed and on PATH
- Free [Pexels API key](https://www.pexels.com/api/)
- [Ollama](https://ollama.ai/) running locally with a model (e.g. `qwen2.5`)  
  (If Ollama is unavailable, the script falls back to a templated narration.)

Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Environment Variables

### Step 1: Add exports to `~/.zshrc`

```bash
echo 'export PEXELS_API_KEY=your_pexels_api_key_here' >> ~/.zshrc
echo 'export OLLAMA_URL=http://127.0.0.1:11434' >> ~/.zshrc
echo 'export OLLAMA_MODEL=qwen2.5' >> ~/.zshrc
echo 'export VOX=en-US-JennyNeural' >> ~/.zshrc
source ~/.zshrc
```

### Step 2: Reference them in `.env`

Create a `.env` file in the project root:

```env
PEXELS_API_KEY=${PEXELS_API_KEY}
OLLAMA_URL=${OLLAMA_URL}
OLLAMA_MODEL=${OLLAMA_MODEL}
VOX=${VOX}
```

Now the project will use whatever values you’ve already saved in `~/.zshrc`.

---

## Usage
Run manually:
```bash
python make_video.py
```

The script will:
- Pick a random topic
- Generate narration (`script_YYYY-MM-DD.txt`)
- Create a voiceover (`voice_YYYY-MM-DD.mp3`)
- Download Pexels stock clips
- Export final video in `daily_videos/daily_video_<topic>_<date>.mp4`
- Save captions alongside as `.srt`

---

## Automate Daily Run
**Linux/macOS (cron):**
```bash
crontab -e
# Run every day at 9:05am
5 9 * * * cd /path/to/project && /bin/bash -lc "source .venv/bin/activate && python make_video.py" >> cron.log 2>&1
```

---

## Output Example
```
daily_videos/
  ├── daily_video_blackout-checklist_2025-10-16.mp4
  ├── daily_video_blackout-checklist_2025-10-16.srt
  ├── script_2025-10-16.txt
  └── voice_2025-10-16.mp3
```

---

## Notes
- Pexels clips are free for personal & commercial use (see [license](https://www.pexels.com/license/)).
- Default runtime target is **30s**; clips are trimmed to 5–12s each.
- You can tweak topics in `RANDOM_TOPICS` inside `make_video.py`.
- For platform uploads (YouTube Shorts, Telegram channel, etc.), extend the script with their APIs.

---

## Roadmap
- Add affiliate link overlay or outro slide
- Auto-upload to YouTube/Telegram
- Smarter clip selection (e.g., keyword match with Ollama summary)
- Personalized script tone (family prep, urban survival, etc.)
