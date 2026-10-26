# 🎮 8-BIT FORGE

**A free 8/16-bit music generator inspired by the NES (Dendy) and Sega Mega Drive.**

Describe a track in plain words, or compose it by hand in a piano roll. 8-BIT FORGE writes chiptune melodies, jingles and sound effects for games, videos or just for fun. Everything runs locally on your computer: no internet, no accounts, no subscriptions.

> **Note:** the app's interface is currently in Russian.

---

## ✨ Features

### 💬 Chat Studio
- Type a request in plain words, e.g. *"sad rainy melody, slow, no vocals"*, and get a finished track.
- Five built-in Forge models: **Melody**, **Ambient**, **Action**, **Jingle**, **SFX**. The model is picked automatically from your request, or you can choose it yourself.
- Tracks have real song form, harmony and motif development, not just random notes.
- 20+ genres: adventure, boss battle, racing, dungeon/horror, space, synthwave, lo-fi, rock/metal, victory fanfare and more.
- Choose the duration (from 3 seconds to 3 minutes), genre and vocals.

> Forge models are music-theory-based algorithms that run fully offline. No data is sent anywhere.

### 🎹 Manual Mode
- Generate by style, key, scale/mode, tempo, density and complexity.
- 5 channels: lead, harmony, bass, arpeggio, drums.
- **NES (Dendy)** or **Sega (FM)** chip sound.
- Piano-roll editor: draw, move, stretch and delete notes.
- Drag to select a region and press **♻ Recreate another piece** to regenerate just that part. The previous version is kept in a cache so you can bring it back.
- Undo / redo (◀ Back / Forward ▶).

### 🔊 Sound
- Per channel: waveform, duty cycle, PWM, ADSR, vibrato, FM, detune, echo, presets.
- Master: bitcrush, sample-rate reduction, smoothing, NES-style 4-bit volume.

### 💾 Export
| What | Format |
|---|---|
| Audio (full track, selection, seamless loop, stems) | WAV, MP3* |
| Notes | MIDI |
| Video with visualizer (16:9, 9:16 for TikTok/Reels/Shorts, 1:1) | MP4* |
| Beat markers for video editing | DaVinci Resolve (.edl), Audacity, CSV, TXT |
| Project | JSON |

\* MP3 and video require [ffmpeg](https://ffmpeg.org/); video also requires Pillow.

### 🎨 Interface
Dark (default) and light themes, with several accent colors.

---

## 🚀 Getting Started

### Ready-to-run app (Windows)
Download `8-BIT FORGE.exe` from [Releases](../../releases) and run it. No installation needed.

### From source
Requires **Python 3.9+** (tkinter ships with standard Python).

```bash
pip install numpy
python Generator_of_music.py
```

Optional:
```bash
pip install pillow   # window icon and video export
```
For MP3 and video export, install [ffmpeg](https://ffmpeg.org/download.html) and add it to your `PATH`.

---

## 🛠 Building the .exe

Built with PyInstaller (the script offers to install it if it's missing):

```bash
python build.py              # single file:  dist/8-BIT FORGE.exe
python build.py --folder     # folder:       dist/8-BIT FORGE/ (starts faster)
python build.py --ffmpeg     # bundle ffmpeg so MP3 and video work on any PC
python build.py --console    # keep a console window for debugging
```

---

## 📁 Project Structure

```
Generator_of_music.py   entry point
build.py                .exe build script
scripts/
├── audio/              sound synthesis, loudness, SFX, ffmpeg
├── core/               song model, constants, music theory, background tasks
├── export/             video and beat markers
├── models_of_ai/       Forge models: request parsing, genres, composers, jingles, SFX
├── music/              composer, track structure
└── ui/                 interface: start screen, chat studio, editor
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). Music you create with 8-BIT FORGE is yours to use freely in your games, videos and other projects, including commercial ones.
