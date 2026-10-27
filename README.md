# 🎮 8-BIT FORGE

**A free 8/16-bit music generator inspired by the NES (Dendy) and Sega Mega Drive.**

Describe a track in plain words, or compose it by hand in a piano roll. 8-BIT FORGE writes chiptune melodies, jingles and sound effects for games, videos or just for fun. It can also import MIDI files and real game music (NES / Sega rips) so you can remix them. Everything runs locally on your computer: no internet, no accounts, no subscriptions.

> **Languages:** the interface is in English by default. Russian can be switched on at any time: use the **EN | RU** switch on the start screen, **EN ⇄ RU** in the chat studio or **View → Language** in the editor. The window rebuilds instantly and your work is kept.

---

## ✨ Features

### 💬 Chat Studio
- Type a request in plain words, e.g. *"sad rainy melody, slow, no vocals"*, and get a finished track.
- Five built-in Forge models: **Melody**, **Ambient**, **Action**, **Jingle**, **SFX**. The model is picked automatically from your request, or you can choose it yourself.
- Tracks have real song form, harmony and motif development, not just random notes.
- 22 genres: adventure, boss battle, racing, dungeon/horror, castle, space, synthwave, lo-fi, rock/metal, victory fanfare and more.
- Choose the duration (from 3 seconds to 3 minutes), genre and vocals (with a choice of voice timbre).
- **☷ Instruments:** tick exactly which instruments play: 10 melody/chord sounds (NES pulses, PWM strings, flute, saw, Sega FM brass, e-piano, bell, organ), 4 basses, drums and arpeggio. Only the ticked ones play, in every model. On **Auto** the model picks the sounds itself and varies them from track to track.
- 22 kinds of sound effects (jump, coin, laser, explosion, power-up, magic, door…), and whole SFX packs for a type of game.
- Every result card: listen, **⚄ another variant**, save as WAV / MP3, or **✎ open in the editor**.
- **☰ Chat history:** every chat is saved automatically. Open **☰ History** in the top bar to go back to an earlier chat with all its tunes, keep generating there, or delete it. Older chats are paged with **Older chats / Newer chats**.

> Forge models are music-theory-based algorithms that run fully offline. No data is sent anywhere.

### 🎹 Manual Mode (editor)
- Generate by style (10 Dendy and Sega presets), key, scale/mode, tempo, density, complexity and swing.
- 6 channels: lead, harmony, bass, arpeggio, drums and voice.
- **NES (Dendy)** or **Sega (FM)** chip sound.
- Piano-roll editor: draw, move, stretch and delete notes; copy, paste, transpose, reverse, quantize, humanize.
- Drag to select a region and press **♻ Recreate another piece** to regenerate just that part. The previous version is kept in a cache so you can bring it back.
- Undo / redo (◀ Back / Forward ▶) with a clickable history of actions.
- **✦ Companion** (`Ctrl+K`): describe a track in words right inside the editor.
- For videos: platform presets (TikTok / Reels, YouTube Shorts, intros, stories, 2-minute backgrounds), exact length in seconds, intro build-up, final chord and a "drop" at a chosen second.

### ⬆ Import
Open with the **⬆ Import** button in the editor, `Ctrl+I`, or **⬆ Import track…** on the start screen.

| File | What you get |
|---|---|
| 8-BIT FORGE project (`.json`) | the project, exactly as saved |
| MIDI (`.mid`, `.midi`) | notes, tempo and tracks; the app's own MIDI exports also get their volume and pan back |
| NES / Dendy (`.nsf`, `.vgm`) | the game's own music player is emulated and the notes are recovered channel by channel: 2 pulses, triangle, noise. If the file has several tunes, you choose which one |
| Sega Mega Drive / Master System (`.vgm`, `.vgz`) | notes of the 6 FM channels, 3 square channels, noise and sampled drums |

Tempo, key and chords are detected automatically, so ♻ Recreate and every other tool works on imported tracks too.

> MP3 / WAV files can't be imported: they contain finished sound, not notes. For game music, look for the NSF or VGM version of the soundtrack.
>
> Not supported yet: NSFe, cartridge expansion chips (VRC6, Namco 163, etc.) and the Japanese Master System FM chip. From such files only the standard channels are read.

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

Loudness targets for publishing: −14 LUFS (YouTube / Spotify), −16 LUFS (Apple / podcasts), −11 LUFS (TikTok / Reels), −9 LUFS (maximum).

\* MP3 and video require [ffmpeg](https://ffmpeg.org/); video also requires Pillow.

### 🎨 Interface
Dark (default) and light themes, several accent colors, animated chat studio.

---

## ⌨ Keyboard Shortcuts (editor)

| Keys | Action |
|---|---|
| `Space` | play / stop |
| `Ctrl+G` | generate a new track |
| `R` | ♻ recreate the selected piece |
| `E` | switch arrangement / piano-roll editor |
| `Ctrl+Z` / `Ctrl+Y` | undo / redo |
| `Ctrl+C` / `Ctrl+V` / `Ctrl+D` | copy / paste / duplicate |
| `Del` | clear the selection |
| `↑` / `↓` (`Shift` = octave) | transpose the selection |
| `Ctrl+O` / `Ctrl+S` | open / save project |
| `Ctrl+I` | import a track |
| `Ctrl+E` | export WAV |
| `Ctrl+K` | ✦ Companion |
| `F`, `+`, `−` | fit to window, zoom in, zoom out |
| `1`…`6` | select a track |
| `D` / `S` / `X` | draw / select / erase tool |
| `←` / `→` | move the cursor (or the selected notes) |
| `L` | loop on / off |
| `M` | mute the current track |

On the start screen, `1` opens the chat studio and `2` opens the editor.

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

### Where your data is stored
| What | Where |
|---|---|
| Settings (theme, language, accent, last folder) | `~/.8bit_forge_prefs.json` |
| Chat history | `~/.8bit_forge_chats/` (one file per chat + `index.json`) |

`~` is your user folder, e.g. `C:\Users\<name>`. Chats store notes and sound settings, not audio, so they stay small; the sound is rebuilt the first time you play a tune from an old chat.

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
├── core/               song model, constants, music theory, translations, settings, chat history, background tasks
├── export/             video and beat markers
├── models_of_ai/       Forge models: request parsing, genres, composers, jingles, SFX
├── music/              composer, track structure, companion, import (MIDI / NSF / VGM)
└── ui/                 interface: start screen, chat studio, editor
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). Music you create with 8-BIT FORGE is yours to use freely in your games, videos and other projects, including commercial ones.
