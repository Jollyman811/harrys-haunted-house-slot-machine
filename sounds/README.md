# Sounds folder

Place your WAV files here. The game looks for these filenames by default (you can change them in `_setup_sounds` in `.venv/main.py`):

- credit.wav — short blip when you press Spin
- chains_loop.wav — looping “rattling chains” ambience during reel movement
- reels_spin_loop.wav — looping spinning reels sound during animation
- win.wav — celebratory sound when a win occurs
- freespin_award.wav — sound when 3+ freespins are awarded
- jackpot_win.wav — big, exciting sound when any jackpot hits

Recommended format
- PCM WAV, 44.1 kHz, 16-bit (mono or stereo). Other formats may work, but WAV is the most reliable with Qt.
- Normalize loudness so they blend well (e.g., around -14 LUFS integrated) and avoid clipping.
- For loops, trim at zero-crossings and consider a tiny fade to make the loop seamless.

Custom filenames
- Edit `_setup_sounds()` in `d:\HHMSlots\.venv\main.py` to point to different filenames if you prefer.

Troubleshooting
- If a sound doesn’t play, check the VS Code Terminal output for a [MISS] message showing the exact path searched.
- If your system lacks QtMultimedia support, the game will run but silently. Install `PyQt5` with multimedia support and ensure audio output is available.
