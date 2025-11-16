# Harry's Haunted House Slot Machine

Halloween‑themed PyQt5 slot machine:
- Animated reels (cycling spin)
- Scatter (3+ freespins symbols) awards free spins
- Progressive jackpots (Mini / Minor / Jackpot / Grand)
- Free spin session total tracker + end summary popup
- Sound effects (WAV) for spin, award, win, jackpot
- Easily moddable Python code

## 1. Requirements
- Python 3.10+ (3.13 supported)
- Pip
- Windows (recommended; PyQt5 wheel availability)

## 2. Clone
```powershell
git clone https://github.com/Jollyman811/HHMSlots.git
cd HHMSlots
```

## 3. Create virtual environment
```powershell
python -m venv .venv
```
This automatically creates `.venv\pyvenv.cfg`.  
If you see a stray `pyvenv.cfg` file in the project root (accidentally committed), move it:
```powershell
move pyvenv.cfg .\.venv\
```
Or delete it and recreate the venv:
```powershell
rmdir /s /q .venv
python -m venv .venv
```

## 4. Activate venv
```powershell
.\.venv\Scripts\Activate.ps1
```
(If PowerShell blocks scripts: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.)

## 5. Install dependencies
```powershell
pip install PyQt5
```

## 6. Assets
Ensure these folders exist (create if missing):
```
images/        -> symbol PNGs (beetle.png, ghost.png, freespins.png, etc.)
animations/    -> GIFs like ghost_win.gif, witch_win.gif, freespins.gif
sounds/        -> credit.wav, chains_loop.wav, reels_spin_loop.wav, win.wav, freespin_award.wav, jackpot_win.wav
```
Missing files will log [MISS] warnings but the app still runs.

## 7. Run
```powershell
python main.py
```

## 8. Optional: Update dependencies later
```powershell
pip install --upgrade PyQt5
```

## 9. Common Issues
- Unknown property text-shadow: remove `text-shadow` lines (Qt style sheets don’t support it).
- No sounds: ensure WAV files present + PyQt5 installed.
- Window opens but images show text: PNG filenames must match symbol names (lowercase).
- Free spins not awarding: need ≥3 `freespins` symbols in the 3x5 grid.

## 10. Contribute
Fork → create feature branch → commit → PR.

## 11. License
MIT (see LICENSE).
