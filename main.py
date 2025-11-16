"""
Harry's Haunted House Slot Machine - Casino Edition (UI Upgraded)

- Casino-style PRNG (Xoshiro256**)
- Virtual reel strips with volatility modes
- 10-line, left-to-right payline evaluation
- Progressive jackpots
- Scatter-triggered free spins with session tracker
- Upgraded haunted-casino PyQt5 UI
"""

import os
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QGridLayout, QVBoxLayout,
    QHBoxLayout, QComboBox, QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont, QMovie
from PyQt5.QtCore import Qt, QTimer, QUrl
try:
    from PyQt5.QtMultimedia import QSoundEffect
    _HAS_SOUND = True
except Exception as _e:
    print(f"[WARN] QtMultimedia not available for sounds: {_e}")
    _HAS_SOUND = False


# ---------------------------------------------------------------------------
# Project root / assets
# ---------------------------------------------------------------------------

def resolve_project_root() -> Path:
    """Return the directory that contains the asset folders."""
    current = Path(__file__).resolve().parent
    if not (current / "images").exists() and (current.parent / "images").exists():
        return current.parent
    return current


PROJECT_ROOT = resolve_project_root()
IMAGES_DIR = PROJECT_ROOT / "images"
ANIMATIONS_DIR = PROJECT_ROOT / "animations"
SOUNDS_DIR = PROJECT_ROOT / "sounds"

if not IMAGES_DIR.exists():
    print(f"[WARN] Images directory not found at {IMAGES_DIR}")
if not ANIMATIONS_DIR.exists():
    print(f"[WARN] Animations directory not found at {ANIMATIONS_DIR}")
if not SOUNDS_DIR.exists():
    print(f"[WARN] Sounds directory not found at {SOUNDS_DIR}")


# ---------------------------------------------------------------------------
# Sound Manager
# ---------------------------------------------------------------------------

class SoundManager:
    def __init__(self):
        self.effects = {}
        self.enabled = _HAS_SOUND

    def load(self, name: str, filename: str, volume: float = 0.6, loop: bool = False):
        if not self.enabled:
            return
        path = SOUNDS_DIR / filename
        if not path.exists():
            print(f"[MISS] Sound not found: {path} — add your .wav file or change the filename in code.")
            return
        eff = QSoundEffect()
        eff.setSource(QUrl.fromLocalFile(str(path)))
        eff.setVolume(max(0.0, min(1.0, volume)))
        if loop:
            eff.setLoopCount(-2)  # infinite
        self.effects[name] = eff

    def play(self, name: str):
        if not self.enabled:
            return
        eff = self.effects.get(name)
        if eff:
            eff.stop()
            eff.play()

    def start_loop(self, name: str):
        if not self.enabled:
            return
        eff = self.effects.get(name)
        if eff:
            eff.setLoopCount(-2)
            eff.play()

    def stop(self, name: str):
        if not self.enabled:
            return
        eff = self.effects.get(name)
        if eff:
            eff.stop()


# ---------------------------------------------------------------------------
# Casino-style RNG: Xoshiro256**
# ---------------------------------------------------------------------------

class Xoshiro256StarStar:
    """
    Simple Python implementation of the xoshiro256** PRNG.
    Good quality PRNG used in many simulations and games.
    """

    def __init__(self, seed_bytes: Optional[bytes] = None):
        if seed_bytes is None:
            seed_bytes = os.urandom(32)  # 256 bits
        if len(seed_bytes) < 32:
            seed_bytes = (seed_bytes * (32 // len(seed_bytes) + 1))[:32]
        self.s = [
            int.from_bytes(seed_bytes[0:8], "little"),
            int.from_bytes(seed_bytes[8:16], "little"),
            int.from_bytes(seed_bytes[16:24], "little"),
            int.from_bytes(seed_bytes[24:32], "little"),
        ]
        if not any(self.s):
            # avoid all-zero state
            self.s[0] = 1

    @staticmethod
    def _rotl(x: int, k: int) -> int:
        return ((x << k) & ((1 << 64) - 1)) | (x >> (64 - k))

    def next_uint64(self) -> int:
        s0, s1, s2, s3 = self.s
        result = self._rotl((s1 * 5) & ((1 << 64) - 1), 7) * 9 & ((1 << 64) - 1)

        t = (s1 << 17) & ((1 << 64) - 1)

        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= t
        s3 = self._rotl(s3, 45)

        self.s = [s0, s1, s2, s3]
        return result

    def random(self) -> float:
        """Return float in [0, 1)."""
        return (self.next_uint64() >> 11) * (1.0 / (1 << 53))

    def randint(self, n: int) -> int:
        """Return int in [0, n)."""
        if n <= 0:
            raise ValueError("n must be positive")
        return self.next_uint64() % n


# ---------------------------------------------------------------------------
# Slot Machine Math Config
# ---------------------------------------------------------------------------

# Reel-window size
REELS = 5
ROWS = 3

# Symbols in use. Make sure you have matching PNGs in /images where possible.
SYMBOLS = [
    "beetle", "spider", "bat", "ghost", "goblin",
    "skeleton", "mummy", "vampire", "witch", "werewolf",
    "haunted_house", "freespins"
]

SCATTER_SYMBOL = "freespins"  # pays via feature, not line pays

# Paytable: bet * multiplier for 3, 4, 5 of a kind.
PAYTABLE = {
    "beetle":        {3: 0.5, 4: 1.0, 5: 2.0},
    "spider":        {3: 0.8, 4: 1.5, 5: 3.0},
    "bat":           {3: 1.0, 4: 2.0, 5: 4.0},
    "ghost":         {3: 1.2, 4: 2.5, 5: 5.0},
    "goblin":        {3: 1.5, 4: 3.0, 5: 7.0},
    "skeleton":      {3: 2.0, 4: 4.0, 5: 9.0},
    "mummy":         {3: 2.5, 4: 5.0, 5: 12.0},
    "vampire":       {3: 3.0, 4: 7.0, 5: 15.0},
    "witch":         {3: 4.0, 4: 10.0, 5: 25.0},
    "werewolf":      {3: 5.0, 4: 15.0, 5: 40.0},
    "haunted_house": {3: 8.0, 4: 25.0, 5: 80.0},
    # scatter handled via feature only
}

# 10 classic paylines: each list element is row index per reel [0, 1, 2]
PAYLINES = [
    [1, 1, 1, 1, 1],  # middle
    [0, 0, 0, 0, 0],  # top
    [2, 2, 2, 2, 2],  # bottom
    [0, 1, 2, 1, 0],  # V
    [2, 1, 0, 1, 2],  # inverted V
    [0, 0, 1, 2, 2],
    [2, 2, 1, 0, 0],
    [0, 1, 1, 1, 2],
    [2, 1, 1, 1, 0],
    [1, 0, 1, 2, 1],
]

BET_OPTIONS = [1, 2, 3, 5, 10, 20, 50, 100]
START_BALANCE = 10_000


def build_reel_strip(volatility: str = "MEDIUM") -> list:
    """
    Build a single virtual reel strip for the given volatility profile.

    LOW    = more low-pay symbols, fewer top symbols → gentle play
    MEDIUM = balanced
    HIGH   = fewer low-pay, more mid/top → spikier
    """
    base_counts = {
        "beetle": 24,
        "spider": 20,
        "bat": 18,
        "ghost": 16,
        "goblin": 10,
        "skeleton": 8,
        "mummy": 6,
        "vampire": 4,
        "witch": 3,
        "werewolf": 2,
        "haunted_house": 1,
        SCATTER_SYMBOL: 3,
    }

    counts = base_counts.copy()

    v = volatility.upper()
    if v == "LOW":
        counts["beetle"] += 8
        counts["spider"] += 6
        counts["bat"] += 4
        counts["witch"] = max(1, counts["witch"] - 1)
        counts["werewolf"] = max(1, counts["werewolf"] - 1)
        counts["haunted_house"] = 1
        counts[SCATTER_SYMBOL] = max(1, counts[SCATTER_SYMBOL] - 1)
    elif v == "HIGH":
        counts["beetle"] = max(10, counts["beetle"] - 8)
        counts["spider"] = max(8, counts["spider"] - 6)
        counts["ghost"] += 2
        counts["goblin"] += 2
        counts["skeleton"] += 1
        counts["mummy"] += 1
        counts["werewolf"] += 1
        counts["haunted_house"] += 1
    # MEDIUM = base

    strip = []
    for sym, n in counts.items():
        strip.extend([sym] * n)
    return strip


# ---------------------------------------------------------------------------
# Casino-grade Haunted House Slot Engine
# ---------------------------------------------------------------------------

class HauntedHouseSlot:
    def __init__(self, volatility: str = "MEDIUM", rtp_mode: str = "STANDARD"):
        self.balance = START_BALANCE
        self.reels = REELS
        self.rows = ROWS
        self.volatility = volatility.upper()
        self.rtp_mode = rtp_mode.upper()
        self.free_spins = 0
        self.in_free_spins = False

        # Free-spin session tracking
        self.free_spins_session_total = 0.0

        # Progressive jackpots
        self.jackpots = {
            "mini":   {"base": 20.0,   "current": 20.0},
            "minor":  {"base": 50.0,   "current": 50.0},
            "jackpot": {"base": 500.0, "current": 500.0},
            "grand":  {"base": 2500.0, "current": 2500.0},
        }
        self._jackpot_base_probs = {
            "mini":   1.0 / 500.0,
            "minor":  1.0 / 2000.0,
            "jackpot": 1.0 / 25000.0,
            "grand":  1.0 / 500000.0,
        }

        # RNG
        self.rng = Xoshiro256StarStar()

        # Build reel strips for each reel
        strip = build_reel_strip(self.volatility)
        self.reel_strips = [strip[:] for _ in range(self.reels)]

        # RTP scaling factor (simple, linear)
        if self.rtp_mode == "LOOSE":
            self.rtp_multiplier = 1.1
        elif self.rtp_mode == "TIGHT":
            self.rtp_multiplier = 0.9
        else:
            self.rtp_multiplier = 1.0

    # ------------- Core spin cycle -------------

    def spin(self, bet: int):
        """
        Perform a casino-style spin:

        - If not in free spins: deduct bet & increment jackpots.
        - Generate reel stops & visible 3x5 grid from virtual strips.
        - Evaluate all paylines (left-to-right).
        - Apply scatter logic for free spins.
        - Roll for progressive jackpots.
        """
        using_free_spin = self.free_spins > 0
        self.in_free_spins = using_free_spin

        if not using_free_spin:
            if bet not in BET_OPTIONS or bet > self.balance:
                return {"error": "Invalid bet or insufficient balance."}
            self.balance -= bet

            inc = round(0.01 * bet, 2)
            for j in self.jackpots.values():
                j["current"] = round(j["current"] + inc, 2)

        grid, stop_indices = self._generate_grid()

        win_details, base_win = self._evaluate_lines(grid, bet, using_free_spin)

        freespins_cells, free_spins_awarded = self._evaluate_scatters(grid)

        jackpot_wins = self._roll_jackpots(bet)
        jackpot_sum = round(sum(w["amount"] for w in jackpot_wins), 2)

        total_win = round(base_win + jackpot_sum, 2)
        self.balance = round(self.balance + total_win, 2)

        free_spins_just_ended = False
        free_spins_session_final = None

        if using_free_spin:
            self.free_spins -= 1
            self.free_spins_session_total = round(self.free_spins_session_total + total_win, 2)
            if self.free_spins == 0:
                free_spins_just_ended = True
                free_spins_session_final = round(self.free_spins_session_total, 2)
                self.free_spins_session_total = 0.0

        result = {
            "grid": grid,
            "bet": bet,
            "win": total_win,
            "balance": self.balance,
            "win_details": win_details,
            "free_spins": self.free_spins,
            "in_free_spins": self.in_free_spins,
            "freespins_cells": freespins_cells if free_spins_awarded else [],
            "free_spins_awarded": free_spins_awarded,
            "jackpot_wins": jackpot_wins,
            "jackpots": {k: round(v["current"], 2) for k, v in self.jackpots.items()},
            "free_spins_session_total": round(self.free_spins_session_total, 2),
            "free_spins_session_final": free_spins_session_final,
            "free_spins_just_ended": free_spins_just_ended,
        }

        return result

    # ------------- Reel / grid generation -------------

    def _generate_grid(self):
        """
        From each reel strip, pick a random stop index and show 3 symbols:
        top = index-1, mid = index, bottom = index+1 (with wrap).
        Returns (grid, stop_indices).
        """
        grid = [[None for _ in range(self.reels)] for _ in range(self.rows)]
        stop_indices = []
        for reel_idx in range(self.reels):
            strip = self.reel_strips[reel_idx]
            n = len(strip)
            stop = self.rng.randint(n)
            stop_indices.append(stop)
            grid[0][reel_idx] = strip[(stop - 1) % n]
            grid[1][reel_idx] = strip[stop]
            grid[2][reel_idx] = strip[(stop + 1) % n]
        return grid, stop_indices

    # ------------- Line evaluation -------------

    def _evaluate_lines(self, grid, bet: int, using_free_spin: bool):
        """
        Evaluate all paylines for wins.
        Left-to-right, 3+ identical symbols (scatter does not pay lines).
        """
        win_details = []
        total = 0.0

        fs_multiplier = 2.0 if using_free_spin else 1.0

        for payline_index, line in enumerate(PAYLINES):
            symbols = []
            coords = []
            for reel_idx, row_idx in enumerate(line):
                sym = grid[row_idx][reel_idx]
                symbols.append(sym)
                coords.append((row_idx, reel_idx))

            first = symbols[0]
            if first == SCATTER_SYMBOL:
                continue
            run_len = 1
            for i in range(1, self.reels):
                if symbols[i] == first:
                    run_len += 1
                else:
                    break

            if run_len >= 3 and first in PAYTABLE:
                base_mult = PAYTABLE[first].get(run_len, 0.0)
                line_win = bet * base_mult * self.rtp_multiplier * fs_multiplier
                if line_win > 0:
                    total += line_win
                    path = coords[:run_len]
                    win_details.append({
                        "type": "adjacent_path",
                        "character": first,
                        "count": run_len,
                        "path": path,
                        "payline_index": payline_index,
                        "win": round(line_win, 2),
                    })

        return win_details, round(total, 2)

    # ------------- Scatter / free spins -------------

    def _evaluate_scatters(self, grid):
        """
        Count scatter symbols anywhere; award free spins on 3+.
        """
        scatter_positions = []
        for r in range(self.rows):
            for c in range(self.reels):
                if grid[r][c] == SCATTER_SYMBOL:
                    scatter_positions.append((r, c))

        count = len(scatter_positions)
        free_spins_awarded = False

        if count >= 3:
            if count == 3:
                award = 10
            elif count == 4:
                award = 12
            else:
                award = 15
            self.free_spins += award
            free_spins_awarded = True

        return scatter_positions, free_spins_awarded

    # ------------- Progressive jackpots -------------

    def _roll_jackpots(self, bet: int):
        """
        Randomly award jackpots. Probability scales with bet size.
        """
        wins = []
        scale = max(0.1, min(5.0, bet / 10.0))
        for name, data in self.jackpots.items():
            p = self._jackpot_base_probs[name] * scale
            p = min(p, 0.25)
            if self.rng.random() < p:
                amt = round(data["current"], 2)
                wins.append({"name": name, "amount": amt})
                data["current"] = data["base"]
        return wins


# ---------------------------------------------------------------------------
# PyQt5 UI
# ---------------------------------------------------------------------------

class SlotMachineUI(QWidget):
    def __init__(self):
        super().__init__()
        self._apply_base_style()

        self.setWindowTitle("Harry's Haunted House Slot Machine - Casino Edition")
        # volatility: "LOW"/"MEDIUM"/"HIGH", rtp_mode: "TIGHT"/"STANDARD"/"LOOSE"
        self.game = HauntedHouseSlot(volatility="MEDIUM", rtp_mode="STANDARD")
        self.sounds = SoundManager()
        self._setup_sounds()
        self._grid_gif_movies = []

        # Reel spin animation state
        self.is_spinning = False
        self.spin_timer = None
        self.spin_tick_count = 0
        self.spin_total_ticks = 0
        self.target_result = None

        # current grid state
        from random import choice
        self.current_grid = [[choice(SYMBOLS) for _ in range(self.game.reels)] for _ in range(self.game.rows)]

        # Free spins visual mode
        self._was_in_free_spins = False
        self.free_spin_pulse_timer = None

        self.init_ui()

    # --- Base style with optional background image ---

    def _apply_base_style(self):
        """
        Apply base haunted casino style with optional background image.
        """
        bg_path = IMAGES_DIR / "haunted_background.jpg"
        if bg_path.exists():
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: #05030a;
                    background-image: url("{bg_path.as_posix()}");
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                    color: #ffffff;
                }}
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: qlineargradient(
                        spread:pad,
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #05030a, stop:1 #12001f
                    );
                    color: #ffffff;
                }
            """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # --- Title + subtitle ---
        title = QLabel("Harry's Haunted House")
        title.setFont(QFont("Papyrus", 30, QFont.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                padding: 4px 8px;
                color: #ffd700;
                text-shadow: 0px 0px 8px #b66dff;
            }
        """)
        subtitle = QLabel("Haunted High-Roller Edition")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                color: #a8b0ff;
                font-size: 11pt;
                letter-spacing: 1px;
            }
        """)
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # --- Jackpot strip inside a glass panel ---
        jp_frame = QWidget()
        jp_frame.setStyleSheet("""
            QWidget {
                background-color: rgba(5, 5, 20, 180);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 30);
            }
        """)
        jp_layout_outer = QHBoxLayout(jp_frame)
        jp_layout_outer.setContentsMargins(12, 8, 12, 8)
        jp_layout_outer.setSpacing(10)

        self.jackpot_labels = {}
        for name, color in [
            ("mini", "#9acd32"),
            ("minor", "#00ced1"),
            ("jackpot", "#ffa500"),
            ("grand", "#ff1493"),
        ]:
            block = QWidget()
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(8, 4, 8, 4)
            block_layout.setSpacing(2)
            tier = QLabel(name.upper())
            tier.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-weight: bold;
                    font-size: 9pt;
                }}
            """)
            lbl = QLabel("$0.00")
            lbl.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12pt;
                }
            """)
            self.jackpot_labels[name] = lbl
            block_layout.addWidget(tier)
            block_layout.addWidget(lbl)
            jp_layout_outer.addWidget(block)

        main_layout.addWidget(jp_frame)

        # --- Balance + last win row ---
        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)

        self.balance_label = QLabel(f"Balance: ${self.game.balance:.2f}")
        self.balance_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.balance_label.setStyleSheet("""
            QLabel {
                padding: 6px 10px;
                border-radius: 10px;
                background-color: rgba(0, 0, 0, 150);
                color: #35e0ff;
            }
        """)

        self.total_win_label = QLabel("Last Win: $0.00")
        self.total_win_label.setFont(QFont("Arial", 12))
        self.total_win_label.setStyleSheet("""
            QLabel {
                padding: 4px 8px;
                border-radius: 10px;
                background-color: rgba(0, 0, 0, 120);
                color: #ffd700;
            }
        """)

        stats_row.addWidget(self.balance_label)
        stats_row.addStretch()
        stats_row.addWidget(self.total_win_label)
        main_layout.addLayout(stats_row)

        # --- Reel cabinet frame ---
        cabinet = QWidget()
        cabinet.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 5, 30, 230);
                border-radius: 20px;
                border: 2px solid rgba(255, 255, 255, 40);
            }
        """)
        cabinet_layout = QVBoxLayout(cabinet)
        cabinet_layout.setContentsMargins(16, 16, 16, 16)
        cabinet_layout.setSpacing(10)

        # Free spins overlay (banner over reels)
        self.fs_overlay = QLabel("")
        self.fs_overlay.setFont(QFont("Arial", 18, QFont.Bold))
        self.fs_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fs_overlay.setStyleSheet("""
            QLabel {
                color: #ffd700;
                padding: 4px 10px;
            }
        """)
        self.fs_overlay.setVisible(False)
        cabinet_layout.addWidget(self.fs_overlay)

        # Reels grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)
        self.grid_labels = [[QLabel() for _ in range(self.game.reels)] for _ in range(self.game.rows)]
        for r in range(self.game.rows):
            for c in range(self.game.reels):
                lbl = self.grid_labels[r][c]
                lbl.setFixedSize(150, 150)
                lbl.setStyleSheet("""
                    QLabel {
                        border-radius: 12px;
                        border: 2px solid #444;
                        background-color: qradialgradient(
                            cx:0.5, cy:0.5, radius:0.8,
                            fx:0.5, fy:0.5,
                            stop:0 #111111, stop:1 #050509
                        );
                    }
                """)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(lbl, r, c)
        cabinet_layout.addLayout(self.grid_layout)

        main_layout.addWidget(cabinet)

        # --- Controls row: bet + spin ---
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 10, 0, 0)
        controls_row.setSpacing(20)

        bet_panel = QWidget()
        bet_panel_layout = QVBoxLayout(bet_panel)
        bet_panel_layout.setContentsMargins(8, 4, 8, 4)
        bet_panel_layout.setSpacing(4)
        bet_label = QLabel("BET PER SPIN")
        bet_label.setStyleSheet("""
            QLabel {
                color: #d0d0ff;
                font-size: 10pt;
                letter-spacing: 1px;
            }
        """)
        bet_row = QHBoxLayout()
        dollar = QLabel("$")
        dollar.setStyleSheet("QLabel { color: #ffffff; }")
        bet_row.addWidget(dollar)
        self.bet_combo = QComboBox()
        for b in BET_OPTIONS:
            self.bet_combo.addItem(str(b), b)
        self.bet_combo.setStyleSheet("""
            QComboBox {
                background-color: #111;
                color: #fff;
                border-radius: 8px;
                padding: 4px 8px;
                border: 1px solid #555;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #111;
                color: #fff;
                selection-background-color: #333;
            }
        """)
        bet_row.addWidget(self.bet_combo)
        bet_panel_layout.addWidget(bet_label)
        bet_panel_layout.addLayout(bet_row)

        controls_row.addWidget(bet_panel)
        controls_row.addStretch()

        # Big Spin button
        self.spin_btn = QPushButton("SPIN")
        self.spin_btn.setFont(QFont("Arial", 18, QFont.Bold))
        self.spin_btn.setFixedSize(200, 70)
        self.spin_btn.setStyleSheet("""
            QPushButton {
                background-color: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.8,
                    fx:0.5, fy:0.5,
                    stop:0 #ffb347, stop:1 #ff8300
                );
                color: #1b0500;
                border-radius: 35px;
                border: 3px solid #ffe0a0;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.8,
                    fx:0.5, fy:0.5,
                    stop:0 #ffd47a, stop:1 #ff9f1a
                );
            }
            QPushButton:pressed {
                background-color: #ff7a00;
                border: 3px solid #ffaa33;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #999;
                border: 3px solid #555;
            }
        """)
        self.spin_btn.clicked.connect(self.spin)
        controls_row.addWidget(self.spin_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        controls_row.addStretch()
        main_layout.addLayout(controls_row)

        # --- Win details + free spins label ---
        self.win_details_label = QLabel("")
        self.win_details_label.setFont(QFont("Arial", 11))
        self.win_details_label.setTextFormat(Qt.TextFormat.RichText)
        self.win_details_label.setWordWrap(True)
        self.win_details_label.setStyleSheet("""
            QLabel {
                margin-top: 8px;
                padding: 6px 10px;
                border-radius: 10px;
                background-color: rgba(0, 0, 0, 150);
                color: #ffffff;
            }
        """)
        main_layout.addWidget(self.win_details_label)

        self.free_spins_label = QLabel("")
        self.free_spins_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.free_spins_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.free_spins_label.setStyleSheet("""
            QLabel {
                margin-top: 4px;
                color: #ffd700;
            }
        """)
        main_layout.addWidget(self.free_spins_label)

        self.setLayout(main_layout)

        # Initial random grid
        self.update_grid(self.current_grid)
        self._refresh_jackpots()

    def _setup_sounds(self):
        self.sounds.load("credit", "credit.wav", volume=0.5)
        self.sounds.load("chains", "chains_loop.wav", volume=0.4, loop=True)
        self.sounds.load("spin", "reels_spin_loop.wav", volume=0.35, loop=True)
        self.sounds.load("win", "win.wav", volume=0.7)
        self.sounds.load("freespin_award", "freespin_award.wav", volume=0.8)
        self.sounds.load("jackpot", "jackpot_win.wav", volume=0.9)

    def _refresh_jackpots(self):
        for name, data in self.game.jackpots.items():
            lbl = self.jackpot_labels.get(name)
            if lbl:
                lbl.setText(f"${data['current']:.2f}")

    # --- Free spins visual helpers ---

    def _enter_free_spins_mode(self):
        if self.free_spin_pulse_timer is None:
            self.free_spin_pulse_timer = QTimer(self)
            self.free_spin_pulse_timer.timeout.connect(self._pulse_free_spin_border)
        self._pulse_on = False
        self.free_spin_pulse_timer.start(300)
        self._apply_free_spin_style(True)

    def _exit_free_spins_mode(self):
        if self.free_spin_pulse_timer:
            self.free_spin_pulse_timer.stop()
        self._apply_free_spin_style(False)
        self.fs_overlay.setVisible(False)

    def _apply_free_spin_style(self, on: bool):
        if on:
            self.setStyleSheet("""
                QWidget {
                    background-color: qlineargradient(
                        spread:pad,
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1b0033, stop:1 #35005d
                    );
                    color: #ffffff;
                }
            """)
            border = "2px solid #b66dff"
            self.fs_overlay.setText("🎃 FREE SPINS MODE 🎃")
            self.fs_overlay.setVisible(True)
        else:
            self._apply_base_style()
            border = "2px solid #444"
            self.fs_overlay.setVisible(False)

        for r in range(self.game.rows):
            for c in range(self.game.reels):
                self.grid_labels[r][c].setStyleSheet(f"""
                    QLabel {{
                        border-radius: 12px;
                        border: {border};
                        background-color: qradialgradient(
                            cx:0.5, cy:0.5, radius:0.8,
                            fx:0.5, fy:0.5,
                            stop:0 #111111, stop:1 #050509
                        );
                    }}
                """)

    def _pulse_free_spin_border(self):
        self._pulse_on = not getattr(self, "_pulse_on", False)
        border = "2px solid #ffdd55" if self._pulse_on else "2px solid #b66dff"
        for r in range(self.game.rows):
            for c in range(self.game.reels):
                self.grid_labels[r][c].setStyleSheet(f"""
                    QLabel {{
                        border-radius: 12px;
                        border: {border};
                        background-color: qradialgradient(
                            cx:0.5, cy:0.5, radius:0.8,
                            fx:0.5, fy:0.5,
                            stop:0 #111111, stop:1 #050509
                        );
                    }}
                """)

    # --- Grid & animations ---

    def update_grid(self, grid):
        self.current_grid = [row[:] for row in grid]
        for r in range(self.game.rows):
            for c in range(self.game.reels):
                char = grid[r][c]
                img_path = IMAGES_DIR / f"{char}.png"
                lbl = self.grid_labels[r][c]
                pixmap = QPixmap(str(img_path))
                if not pixmap.isNull():
                    lbl.setPixmap(
                        pixmap.scaled(
                            140, 140,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                    )
                    lbl.setText("")
                else:
                    lbl.setPixmap(QPixmap())
                    lbl.setText(char)
                    if not img_path.exists():
                        print(f"[MISS] Image not found: {img_path}")

    def show_grid_animation(self, win, grid):
        character = win["character"].lower()
        win_amt = win["win"]
        anim_type = "celebration" if win_amt < 5 else "win"
        gif_path = ANIMATIONS_DIR / f"{character}_{anim_type}.gif"
        if not gif_path.exists():
            print(f"[MISS] Animation not found: {gif_path}")
            return

        cells = win.get("path", [])
        for (row, col) in cells:
            lbl = self.grid_labels[row][col]
            lbl.clear()
            movie = QMovie(str(gif_path))
            movie.setScaledSize(lbl.size())
            lbl.setMovie(movie)
            movie.start()
            lbl._movie_refs = getattr(lbl, '_movie_refs', [])
            lbl._movie_refs.append(movie)
            self._grid_gif_movies.append(movie)

    # --- Spin button handlers ---

    def spin(self):
        if self.is_spinning:
            return

        for lbl_row in self.grid_labels:
            for lbl in lbl_row:
                if hasattr(lbl, '_movie_refs'):
                    lbl.clear()
        self._grid_gif_movies.clear()

        bet = self.bet_combo.currentData()
        result = self.game.spin(bet)
        if "error" in result:
            QMessageBox.warning(self, "Error", result["error"])
            return

        self.target_result = result
        self.is_spinning = True
        self.spin_tick_count = 0
        self.spin_total_ticks = 8
        interval_ms = 50

        self.spin_btn.setEnabled(False)
        self.win_details_label.setText("Spinning...")

        if self.current_grid is None:
            from random import choice
            self.current_grid = [[choice(SYMBOLS) for _ in range(self.game.reels)] for _ in range(self.game.rows)]

        self.sounds.play("credit")
        self.sounds.start_loop("chains")
        self.sounds.start_loop("spin")

        self.spin_timer = QTimer(self)
        self.spin_timer.timeout.connect(self._advance_reels)
        self.spin_timer.start(interval_ms)

    def _advance_reels(self):
        from random import choice
        for c in range(self.game.reels):
            for r in range(self.game.rows - 1, 0, -1):
                self.current_grid[r][c] = self.current_grid[r - 1][c]
            self.current_grid[0][c] = choice(SYMBOLS)
        self.update_grid(self.current_grid)
        self.spin_tick_count += 1
        if self.spin_tick_count >= self.spin_total_ticks:
            if self.spin_timer:
                self.spin_timer.stop()
            self._finish_spin()

    def _finish_spin(self):
        if not self.target_result:
            self.is_spinning = False
            self.spin_btn.setEnabled(True)
            return

        final_grid = self.target_result["grid"]
        self.update_grid(final_grid)
        self.is_spinning = False
        self.spin_btn.setEnabled(True)

        self.sounds.stop("chains")
        self.sounds.stop("spin")

        self._display_result(self.target_result)
        self.target_result = None

    # --- Display results ---

    def _display_result(self, result):
        self.balance_label.setText(f"Balance: ${self.game.balance:.2f}")
        self.total_win_label.setText(f"Last Win: ${result['win']:.2f}")

        jps = result.get("jackpots", {})
        for name, lbl in self.jackpot_labels.items():
            if name in jps:
                lbl.setText(f"${jps[name]:.2f}")

        if result["win_details"]:
            details_lines = []
            for win in result["win_details"]:
                details_lines.append(
                    f"{win['character'].capitalize()} x{win['count']} "
                    f"(Line {win['payline_index'] + 1}) - "
                    f"<b>${win['win']:.2f}</b>"
                )
                self.show_grid_animation(win, result["grid"])
            self.win_details_label.setText("<br>".join(details_lines))
        else:
            self.win_details_label.setText("No win this spin.")

        if result.get("jackpot_wins"):
            jp_msgs = [f"{w['name'].capitalize()} Jackpot +${w['amount']:.2f}!" for w in result["jackpot_wins"]]
            self.win_details_label.setText(self.win_details_label.text() + "<br>" + " ".join(jp_msgs))
            self.sounds.play("jackpot")

        if result['win'] > 0:
            self.sounds.play("win")

        if result.get("free_spins", 0) > 0:
            fs_text = f"Free Spins: {result['free_spins']}"
            if result.get("free_spins_awarded"):
                fs_text += " (+ spins awarded!)"
                self.sounds.play("freespin_award")
            self.free_spins_label.setText(fs_text)
        else:
            self.free_spins_label.setText("")

        if result.get("freespins_cells"):
            gif_path = ANIMATIONS_DIR / "freespins.gif"
            if gif_path.exists():
                for row, col in result["freespins_cells"]:
                    lbl = self.grid_labels[row][col]
                    lbl.clear()
                    movie = QMovie(str(gif_path))
                    movie.setScaledSize(lbl.size())
                    lbl.setMovie(movie)
                    movie.start()
                    lbl._movie_refs = getattr(lbl, '_movie_refs', [])
                    lbl._movie_refs.append(movie)
                    self._grid_gif_movies.append(movie)
            else:
                print(f"[MISS] Free spins animation not found: {gif_path}")

        in_fs = bool(result.get("in_free_spins")) or (result.get("free_spins", 0) > 0)
        if in_fs and not self._was_in_free_spins:
            self._enter_free_spins_mode()
        self._was_in_free_spins = in_fs

        if in_fs:
            total = result.get("free_spins_session_total", 0.0)
            if result.get("free_spins_just_ended"):
                total = result.get("free_spins_session_final", total)
            self.fs_overlay.setText(f"🎃 FREE SPINS MODE 🎃\nTotal: ${total:.2f}")
            self.fs_overlay.setVisible(True)

        if result.get("free_spins_just_ended"):
            final_total = result.get("free_spins_session_final", 0.0)
            QMessageBox.information(self, "Free Spins Complete", f"You won ${final_total:.2f} in free spins!")
            self._exit_free_spins_mode()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SlotMachineUI()
    window.resize(900, 900)
    window.show()
    sys.exit(app.exec_())
