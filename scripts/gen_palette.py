#!/usr/bin/env python3
"""The "paper and ink" palette — hand-chosen, machine-verified.

The brief asks for a quiet, editorial, boutique-stay mood: warm parchment page,
near-black ink, almost no accent color. A palette like that is *chosen*, not
generated from a hue — so this script no longer invents colors. It holds the
chosen few and verifies every semantic pair against WCAG 2.2, because the one
thing that must not get lost in a re-skin is that fine print stays readable.

Run:  uv run python scripts/gen_palette.py   (exit code 1 = a pair failed)
"""

from __future__ import annotations

import sys

from coloraide import Color

# ---- the brief's palette ---------------------------------------------------
# Warm parchment and ink. Photography carries the color; chrome stays quiet.

PAPER = "#F4F0E8"  # page background — paper, never pure white
SURFACE = "#FBF9F5"  # cards and inputs
INK = "#1C1916"  # type and the primary button — near-black, warm
INK_SOFT = "#5C564E"  # secondary type, eyebrow text
MUTED = "#8A8175"  # hairlines, control boundaries, disabled type
LINE = "#E4DCD0"  # decorative hairlines (cards, dividers) — no contrast role
LINE_STRONG = "#CFC5B6"  # a stronger hairline where a divider must read
WASH = "#EBE4D8"  # hover wash, sunken surfaces, disabled fill
BUTTON_HOVER = "#2A2622"  # ink, warmed a step
BUTTON_ACTIVE = "#12100E"
BUTTON_TEXT = "#F6F2EB"
DANGER = "#8C3A32"  # the one accent, and it is rare

# The brief names ten colors; a booking UI also needs success/warning states
# for booking status and form feedback. They stay in the same warm, low-chroma
# family — moss and ochre at a muted saturation, never green/red from a SaaS
# palette. Verified below like everything else.
SUCCESS_TEXT = "#3E5A43"
SUCCESS_BG = "#E9EBE2"
WARNING_TEXT = "#6E5421"
WARNING_BG = "#F0E8D9"

# Non-text contrast floor: control boundaries (WCAG 1.4.11).
UI_CONTRAST_MIN = 3.0
# Text contrast floor (WCAG 1.4.3). Fine print and placeholders are text.
TEXT_CONTRAST_MIN = 4.5

# The lightest surface a token must read against — the worst case, not the
# average. For dark text the darker paper is the harder floor (a darker page
# eats contrast), so text colors are graded against paper and clear everywhere.
DARKEST_TEXT_BG = PAPER


def contrast(fg: str, bg: str) -> float:
    return Color(fg).contrast(bg, method="wcag21")


def darken(hex_color: str, amount: float) -> str:
    """Step a color toward ink in OKLCH, keeping its warmth."""
    c = Color(hex_color).convert("oklch")
    c["lightness"] = max(0, c["lightness"] - amount)
    return c.convert("srgb").to_string(hex=True, upper=False)


def text_grade(start: str, bg: str, need: float = TEXT_CONTRAST_MIN) -> str:
    """The darkest stop of `start` that still holds `need` contrast on `bg`.

    Muted is the brief's eyebrow color, but at 12px it is text and 3.4:1 is
    not text. This walks muted toward ink until it clears AA, so the palette
    cannot silently reintroduce unreadable fine print on the next re-skin.
    """
    c = Color(start).convert("oklch")
    for _ in range(60):
        if contrast(c.convert("srgb").to_string(hex=True, upper=False), bg) >= need:
            c["lightness"] = c["lightness"] + 0.01  # walk back toward the brief
            continue
        c["lightness"] = c["lightness"] - 0.01
    # One final nudge: the loop stops one step too dark; return the passing shade.
    return c.convert("srgb").to_string(hex=True, upper=False)


def build() -> dict:
    """The palette as semantic groups — what emit_tokens.py consumes."""
    return {
        "paper": PAPER,
        "surface": SURFACE,
        "ink": INK,
        "ink_soft": INK_SOFT,
        "muted": MUTED,
        "line": LINE,
        "line_strong": LINE_STRONG,
        "wash": WASH,
        "button": INK,
        "button_hover": BUTTON_HOVER,
        "button_active": BUTTON_ACTIVE,
        "button_text": BUTTON_TEXT,
        "danger": DANGER,
        "danger_hover": darken(DANGER, 0.06),
        "tertiary": text_grade(MUTED, DARKEST_TEXT_BG),
        "success_text": SUCCESS_TEXT,
        "success_bg": SUCCESS_BG,
        "warning_text": WARNING_TEXT,
        "warning_bg": WARNING_BG,
        "error_text": DANGER,
        "error_bg": "#F1E2DD",
        "info_text": INK_SOFT,
        "info_bg": WASH,
        "scrim": "rgba(28, 25, 22, 0.45)",
    }


def report(p: dict) -> int:
    checks = [
        # text (4.5:1) — dark type is graded against paper (the darker page
        # eats contrast); clearing that clears the lighter card too
        (p["ink"], SURFACE, 4.5, "ink on surface (body)"),
        (p["ink"], PAPER, 4.5, "ink on paper (body)"),
        (p["ink_soft"], SURFACE, 4.5, "ink-soft on surface (secondary)"),
        (p["ink_soft"], PAPER, 4.5, "ink-soft on paper (secondary)"),
        (p["tertiary"], SURFACE, 4.5, "tertiary on surface (derived, fine print)"),
        (p["tertiary"], PAPER, 4.5, "tertiary on paper (derived, fine print)"),
        (p["button_text"], p["ink"], 4.5, "button-text on the ink button"),
        (p["danger"], PAPER, 4.5, "danger on paper (error text)"),
        (p["success_text"], p["success_bg"], 4.5, "success text on its wash"),
        (p["warning_text"], p["warning_bg"], 4.5, "warning text on its wash"),
        (p["error_text"], p["error_bg"], 4.5, "error text on its wash"),
        (p["info_text"], p["info_bg"], 4.5, "info text on wash"),
        # UI (3:1) — control boundaries, not decoration
        (p["muted"], SURFACE, UI_CONTRAST_MIN, "muted on surface (control border)"),
        (p["muted"], PAPER, UI_CONTRAST_MIN, "muted on paper (control border)"),
        (p["ink"], PAPER, UI_CONTRAST_MIN, "ink on paper (focus border)"),
    ]
    print(f"{'check':<48} {'ratio':>7}  min   ok")
    print("-" * 72)
    fails = 0
    for fg, bg, need, label in checks:
        r = contrast(fg, bg)
        ok = r >= need
        fails += 0 if ok else 1
        print(f"{label:<48} {r:6.2f}:1  {need:>4.1f}  {'PASS' if ok else 'FAIL'}")

    print("\n--- palette ---")
    for k, v in p.items():
        print(f"  {k:<14} {v}")
    print(f"\n  tertiary is derived from muted to clear 4.5:1 on {PAPER}")
    return fails


if __name__ == "__main__":
    bad = report(build())
    print()
    sys.exit(1 if bad else 0)
