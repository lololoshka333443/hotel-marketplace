#!/usr/bin/env python3
"""Generate the brand palette in OKLCH and verify WCAG contrast.

One brand hue + one neutral hue drive everything: change BRAND_HUE below,
re-run, and the whole brand re-skins. Output is DTCG-ready.

Color math: `coloraide` (reference implementation of OKLab/OKLCH).
Contrast: WCAG 2.2 relative luminance via coloraide's `contrast` (APCA-adjacent,
but we use the WCAG 2.x `contrast` method).
"""

from __future__ import annotations

import sys

from coloraide import Color

# ---- brief (brandkit skill, step 1) ---------------------------------------
# Industry: B2B2C hotel & short-stay marketplace, launch Crimea (Black Sea).
# Audience: guests on mobile, partners on laptop.
# Mood:   "warm travel" — trustworthy, calm, sea-and-sky, photography-first.
# Motion: subtle / calm.

BRAND_HUE = 258.0       # sea-sky blue — trustworthy, not corporate navy
BRAND_CHROMA = 0.11
NEUTRAL_HUE = 260.0     # cool-neutral, same family as brand (no muddy green)
NEUTRAL_CHROMA = 0.006

SUCCESS_HUE, SUCCESS_CHROMA = 150.0, 0.10
WARNING_HUE, WARNING_CHROMA = 75.0, 0.12
DANGER_HUE, DANGER_CHROMA = 27.0, 0.14

WHITE = "#ffffff"
BLACK = "#000000"

# Lightness anchors, matching the reference palette spacing (50 light -> 950 dark).
SHADES = {
    "50": 0.975,
    "100": 0.940,
    "200": 0.890,
    "300": 0.825,
    "400": 0.740,
    "500": 0.645,
    "600": 0.555,
    "700": 0.465,
    "800": 0.380,
    "900": 0.295,
    "950": 0.205,
}


def oklch_hex(L: float, C: float, h: float) -> str:
    """Clamp chroma to the sRGB gamut so shades stay in-gamut."""
    c = Color("oklch", [L, C, h])
    while not c.in_gamut("srgb", tolerance=1e-6) and C > 0:
        C *= 0.97
        c = Color("oklch", [L, C, h])
    return c.convert("srgb").to_string(hex=True, upper=False)


def ramp(hue: float, chroma: float) -> dict[str, str]:
    return {name: oklch_hex(L, chroma, hue) for name, L in SHADES.items()}


def contrast(fg: str, bg: str) -> float:
    return Color(fg).contrast(bg, method="wcag21")


def build() -> dict:
    return {
        "blue": ramp(BRAND_HUE, BRAND_CHROMA),
        "neutral": ramp(NEUTRAL_HUE, NEUTRAL_CHROMA),
        "green": ramp(SUCCESS_HUE, SUCCESS_CHROMA),
        "amber": ramp(WARNING_HUE, WARNING_CHROMA),
        "red": ramp(DANGER_HUE, DANGER_CHROMA),
        "white": WHITE,
        "black": BLACK,
    }


def report(p: dict) -> int:
    fails = 0
    n, b = p["neutral"], p["blue"]
    checks = [
        # (fg, bg, min, label)
        (n["900"], WHITE, 4.5, "body text primary on white"),
        (n["600"], WHITE, 4.5, "secondary text on white"),
        (b["600"], WHITE, 4.5, "primary action bg, white text on it"),
        # blue.600 is the text/link/focus token; blue.500 is reserved for the
        # focus RING (3:1 UI rule only) — so 500 is checked as UI, not as text.
        (b["600"], WHITE, 4.5, "text.link / focus color (blue.600) on white"),
        (b["600"], WHITE, 3.0, "blue.600 UI vs white (3:1 UI)"),
        (b["500"], WHITE, 3.0, "focus ring blue.500 UI vs white (3:1 UI)"),
        (n["500"], WHITE, 3.0, "border.strong on white (3:1 UI)"),
        (b["700"], WHITE, 3.0, "primary-hover on white"),
        # dark mode
        (n["50"], n["950"], 4.5, "dark text primary on dark page"),
        (n["400"], n["950"], 4.5, "dark secondary text on dark page"),
        (b["400"], n["950"], 4.5, "dark link blue.400 on dark page"),
        (b["600"], WHITE, 4.5, "dark primary bg w/ white text"),
        (n["500"], n["950"], 3.0, "dark border.strong on dark page"),
    ]
    print(f"{'check':<52} {'ratio':>7}  min   ok")
    print("-" * 76)
    for fg, bg, need, label in checks:
        r = contrast(fg, bg)
        ok = r >= need
        fails += 0 if ok else 1
        print(f"{label:<52} {r:6.2f}:1  {need:>4.1f}  {'PASS' if ok else 'FAIL'}")

    print("\n--- ramps ---")
    for name in ("blue", "neutral", "green", "amber", "red"):
        print(f"{name:8}", " ".join(p[name][k] for k in SHADES))

    print("\n--- token picks ---")
    print(f"  action.primary       blue.600      {b['600']}")
    print(f"  action.primary-hover blue.700      {b['700']}")
    print(f"  text.primary         neutral.900   {n['900']}")
    print(f"  text.secondary       neutral.600   {n['600']}")
    print(f"  surface.sunken       neutral.50    {n['50']}")
    print(f"  border.default       neutral.200   {n['200']}")
    print(f"  border.strong        neutral.500   {n['500']}")
    print(f"  success-text         green.800     {p['green']['800']}")
    print(f"  warning-text         amber.800     {p['amber']['800']}")
    print(f"  error-text           red.700       {p['red']['700']}")
    return fails


if __name__ == "__main__":
    palette = build()
    bad = report(palette)
    print()
    sys.exit(1 if bad else 0)
