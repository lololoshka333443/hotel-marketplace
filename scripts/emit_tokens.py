#!/usr/bin/env python3
"""Emit the DTCG token files + theme.css from scripts/gen_palette.py.

Run:  uv run python scripts/emit_tokens.py
Writes: web/src/styles/tokens/colors.json, web/src/styles/theme.css
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_palette import (
    BLACK,
    SHADES,
    WHITE,
    build,
    contrast,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "web" / "src" / "styles" / "tokens"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def color(value: str, description: str = "") -> dict:
    out = {"$type": "color", "$value": value}
    if description:
        out["$description"] = description
    return out


def ref(path: str) -> dict:
    return {"$type": "color", "$value": f"{{{path}}}"}


def build_colors_json(p: dict) -> dict:
    ramps = ("blue", "neutral", "green", "amber", "red")
    primitive: dict = {
        hue: {name: color(p[hue][name]) for name in SHADES} for hue in ramps
    }
    primitive["white"] = color(WHITE)
    primitive["black"] = color(BLACK)

    doc = {
        "$schema": "https://design-tokens.github.io/community-group/format/",
        "$description": (
            "Hotel marketplace brand tokens — sea-sky blue, cool neutrals. "
            "Generated in OKLCH; all semantic pairs verified WCAG 2.2 AA "
            "(4.5:1 text, 3:1 UI) in light and dark by scripts/gen_palette.py."
        ),
        "primitive": {
            "$description": "Raw palette — never reference directly in components",
            **primitive,
        },
        "semantic": {
            "$description": "Purpose-based tokens — use these in design and code",
            "action": {
                "primary": ref("primitive.blue.600"),
                "primary-hover": ref("primitive.blue.700"),
                "primary-active": ref("primitive.blue.800"),
                "secondary": ref("primitive.neutral.100"),
                "secondary-hover": ref("primitive.neutral.200"),
                "secondary-active": ref("primitive.neutral.300"),
                "destructive": ref("primitive.red.600"),
                "destructive-hover": ref("primitive.red.700"),
            },
            "feedback": {
                "success-bg": ref("primitive.green.50"),
                "success-text": ref("primitive.green.800"),
                "success-border": ref("primitive.green.300"),
                "success-icon": ref("primitive.green.600"),
                "warning-bg": ref("primitive.amber.50"),
                "warning-text": ref("primitive.amber.800"),
                "warning-border": ref("primitive.amber.300"),
                "warning-icon": ref("primitive.amber.700"),
                "error-bg": ref("primitive.red.50"),
                "error-text": ref("primitive.red.700"),
                "error-border": ref("primitive.red.300"),
                "error-icon": ref("primitive.red.600"),
                "info-bg": ref("primitive.blue.50"),
                "info-text": ref("primitive.blue.800"),
                "info-border": ref("primitive.blue.300"),
                "info-icon": ref("primitive.blue.600"),
            },
            "text": {
                "primary": ref("primitive.neutral.900"),
                "secondary": ref("primitive.neutral.600"),
                "tertiary": ref("primitive.neutral.400"),
                "disabled": ref("primitive.neutral.300"),
                "on-action": ref("primitive.white"),
                "link": ref("primitive.blue.600"),
                "link-hover": ref("primitive.blue.700"),
            },
            "surface": {
                "page": ref("primitive.white"),
                "card": ref("primitive.white"),
                "raised": ref("primitive.white"),
                "sunken": ref("primitive.neutral.50"),
                "overlay": color("rgba(20, 23, 30, 0.5)", "Modal/drawer backdrop"),
                "disabled": ref("primitive.neutral.100"),
            },
            "border": {
                "default": ref("primitive.neutral.200"),
                "strong": ref("primitive.neutral.500"),
                "focus": ref("primitive.blue.500"),
                "error": ref("primitive.red.500"),
                "disabled": ref("primitive.neutral.200"),
            },
            "interactive": {
                "hover-overlay": color("rgba(20, 23, 30, 0.04)"),
                "active-overlay": color("rgba(20, 23, 30, 0.08)"),
                "selected-bg": ref("primitive.blue.50"),
                "selected-border": ref("primitive.blue.200"),
            },
        },
        "component": {
            "$description": "Component-scoped tokens — use in component code",
            "button": {
                "primary-bg": ref("semantic.action.primary"),
                "primary-bg-hover": ref("semantic.action.primary-hover"),
                "primary-bg-active": ref("semantic.action.primary-active"),
                "primary-text": ref("semantic.text.on-action"),
                "secondary-bg": ref("semantic.action.secondary"),
                "secondary-bg-hover": ref("semantic.action.secondary-hover"),
                "secondary-text": ref("semantic.text.primary"),
                "ghost-bg": color("transparent"),
                "ghost-bg-hover": ref("semantic.interactive.hover-overlay"),
                "ghost-text": ref("semantic.text.primary"),
                "destructive-bg": ref("semantic.action.destructive"),
                "destructive-bg-hover": ref("semantic.action.destructive-hover"),
                "destructive-text": ref("semantic.text.on-action"),
                "disabled-bg": ref("semantic.surface.disabled"),
                "disabled-text": ref("semantic.text.disabled"),
            },
            "input": {
                "bg": ref("semantic.surface.card"),
                "bg-disabled": ref("semantic.surface.disabled"),
                "border": ref("semantic.border.default"),
                "border-hover": ref("semantic.border.strong"),
                "border-focus": ref("semantic.border.focus"),
                "border-error": ref("semantic.border.error"),
                "text": ref("semantic.text.primary"),
                "placeholder": ref("semantic.text.tertiary"),
            },
            "card": {
                "bg": ref("semantic.surface.card"),
                "border": ref("semantic.border.default"),
            },
            "badge": {
                "neutral-bg": ref("primitive.neutral.100"),
                "neutral-text": ref("primitive.neutral.700"),
                "primary-bg": ref("primitive.blue.100"),
                "primary-text": ref("primitive.blue.700"),
                "success-bg": ref("primitive.green.100"),
                "success-text": ref("primitive.green.700"),
                "warning-bg": ref("primitive.amber.100"),
                "warning-text": ref("primitive.amber.700"),
                "error-bg": ref("primitive.red.100"),
                "error-text": ref("primitive.red.700"),
            },
        },
        "dark": {
            "$description": "Dark-mode semantic overrides — swap at [data-theme='dark']",
            "text": {
                "primary": ref("primitive.neutral.50"),
                "secondary": ref("primitive.neutral.400"),
                "tertiary": ref("primitive.neutral.500"),
                "disabled": ref("primitive.neutral.600"),
                "on-action": ref("primitive.white"),
                "link": ref("primitive.blue.400"),
                "link-hover": ref("primitive.blue.300"),
            },
            "surface": {
                "page": ref("primitive.neutral.950"),
                "card": ref("primitive.neutral.900"),
                "raised": ref("primitive.neutral.800"),
                "sunken": ref("primitive.black"),
            },
            "border": {
                "default": ref("primitive.neutral.800"),
                "strong": ref("primitive.neutral.500"),
            },
            "action": {
                "primary": ref("primitive.blue.600"),
                "primary-hover": ref("primitive.blue.700"),
                "secondary": ref("primitive.neutral.800"),
                "secondary-hover": ref("primitive.neutral.700"),
            },
        },
    }
    return doc


def css_var(name: str, value: str) -> str:
    return f"  --{name}: {value};"


def build_theme_css(p: dict) -> str:
    b, n = p["blue"], p["neutral"]

    def pair(fg: str, bg: str) -> float:
        return contrast(fg, bg)

    lines = [
        "/* theme.css — the ONE shared token theme. Import this once at the app root.",
        " * Every page/component references these variables; none defines its own colors.",
        " * Generated by scripts/emit_tokens.py from scripts/gen_palette.py.",
        " * Contrast values are measured, not eyeballed (coloraide, WCAG 2.2). */",
        "",
        ":root {",
        css_var("font-sans", 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'),
        css_var("font-mono", '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
        "",
        "  /* surfaces */",
        css_var("color-surface-page", WHITE),
        css_var("color-surface-card", WHITE),
        css_var("color-surface-raised", WHITE),
        css_var("color-surface-sunken", n["50"]),
        css_var("color-surface-disabled", n["100"]),
        "",
        "  /* text */",
        css_var("color-text-primary", n["900"]) + f"  /* {pair(n['900'], WHITE):.2f}:1 */",
        css_var("color-text-secondary", n["600"]) + f"  /* {pair(n['600'], WHITE):.2f}:1 */",
        css_var("color-text-tertiary", n["400"]),
        css_var("color-text-disabled", n["300"]),
        css_var("color-text-on-action", WHITE),
        css_var("color-text-link", b["600"]),
        css_var("color-text-link-hover", b["700"]),
        "",
        "  /* action */",
        css_var("color-action-primary", b["600"]) + f"  /* white on this = {pair(WHITE, b['600']):.2f}:1 */",
        css_var("color-action-primary-hover", b["700"]),
        css_var("color-action-primary-active", b["800"]),
        css_var("color-action-secondary", n["100"]),
        css_var("color-action-secondary-hover", n["200"]),
        css_var("color-action-destructive", p["red"]["600"]) + f"  /* white = {pair(WHITE, p['red']['600']):.2f}:1 */",
        css_var("color-action-destructive-hover", p["red"]["700"]),
        "",
        "  /* borders */",
        css_var("color-border-default", n["200"]),
        css_var("color-border-strong", n["500"]) + f"  /* {pair(n['500'], WHITE):.2f}:1 */",
        css_var("color-border-focus", b["500"]),
        css_var("color-border-error", p["red"]["500"]),
        "",
        "  /* feedback */",
        css_var("color-feedback-success-bg", p["green"]["50"]),
        css_var("color-feedback-success-text", p["green"]["800"]),
        css_var("color-feedback-warning-bg", p["amber"]["50"]),
        css_var("color-feedback-warning-text", p["amber"]["800"]),
        css_var("color-feedback-error-bg", p["red"]["50"]),
        css_var("color-feedback-error-text", p["red"]["700"]),
        css_var("color-feedback-info-bg", b["50"]),
        css_var("color-feedback-info-text", b["800"]),
        "",
        "  /* interactive */",
        css_var("color-interactive-hover", "rgba(20, 23, 30, 0.04)"),
        css_var("color-interactive-active", "rgba(20, 23, 30, 0.08)"),
        css_var("color-interactive-selected-bg", b["50"]),
        css_var("color-interactive-selected-border", b["200"]),
        css_var("color-scrim", "rgba(20, 23, 30, 0.5)"),
        "",
        "  /* focus ring — double ring, 3:1 against surrounding surface */",
        css_var("shadow-focus-ring", f"0 0 0 2px {WHITE}, 0 0 0 4px {b['500']}"),
        "",
        "  /* type — Major Third (1.25) scale; every size is a token */",
        css_var("text-xs", "0.75rem"),
        css_var("text-sm", "0.875rem"),
        css_var("text-base", "1rem"),
        css_var("text-lg", "1.125rem"),
        css_var("text-xl", "1.25rem"),
        css_var("text-2xl", "1.5rem"),
        css_var("text-3xl", "1.875rem"),
        css_var("text-4xl", "2.25rem"),
        css_var("text-5xl", "3rem"),
        css_var("text-6xl", "3.75rem"),
        css_var("leading-tight", "1.25"),
        css_var("leading-normal", "1.5"),
        "",
        "  /* spacing — 4px base scale */",
        css_var("space-1", "0.25rem"),
        css_var("space-2", "0.5rem"),
        css_var("space-3", "0.75rem"),
        css_var("space-4", "1rem"),
        css_var("space-5", "1.25rem"),
        css_var("space-6", "1.5rem"),
        css_var("space-8", "2rem"),
        css_var("space-10", "2.5rem"),
        css_var("space-12", "3rem"),
        css_var("space-16", "4rem"),
        css_var("space-20", "5rem"),
        css_var("space-24", "6rem"),
        "",
        "  /* radius / sizing / motion */",
        css_var("radius-sm", "0.25rem"),
        css_var("radius-button", "0.5rem"),
        css_var("radius-lg", "0.75rem"),
        css_var("radius-xl", "1rem"),
        css_var("radius-full", "9999px"),
        css_var("size-control-sm", "2rem"),
        css_var("size-control-md", "2.5rem"),
        css_var("size-control-lg", "3rem"),
        css_var("opacity-disabled", "0.5"),
        css_var("transition-micro", "150ms ease-out"),
        css_var("shadow-overlay", "0 20px 25px -5px rgba(20, 23, 30, 0.15), 0 8px 10px -6px rgba(20, 23, 30, 0.10)"),
        css_var("z-modal", "50"),
        "",
        "  /* breakpoints (mobile-first) */",
        css_var("bp-sm", "640px"),
        css_var("bp-md", "768px"),
        css_var("bp-lg", "1024px"),
        css_var("bp-xl", "1280px"),
        css_var("bp-2xl", "1536px"),
        "}",
        "",
        ':root[data-theme="dark"] {',
        "  /* surfaces */",
        css_var("color-surface-page", n["950"]),
        css_var("color-surface-card", n["900"]),
        css_var("color-surface-raised", n["800"]),
        css_var("color-surface-sunken", BLACK),
        "",
        "  /* text */",
        css_var("color-text-primary", n["50"]) + f"  /* {pair(n['50'], n['950']):.2f}:1 */",
        css_var("color-text-secondary", n["400"]) + f"  /* {pair(n['400'], n['950']):.2f}:1 */",
        css_var("color-text-tertiary", n["500"]),
        css_var("color-text-disabled", n["600"]),
        css_var("color-text-on-action", WHITE),
        css_var("color-text-link", b["400"]) + f"  /* lightened: {pair(b['400'], n['950']):.2f}:1 */",
        css_var("color-text-link-hover", b["300"]),
        "",
        "  /* action */",
        css_var("color-action-primary", b["600"]) + f"  /* white = {pair(WHITE, b['600']):.2f}:1, dark-safe */",
        css_var("color-action-primary-hover", b["700"]),
        css_var("color-action-secondary", n["800"]),
        css_var("color-action-secondary-hover", n["700"]),
        css_var("color-action-destructive", p["red"]["600"]),
        css_var("color-action-destructive-hover", p["red"]["700"]),
        "",
        "  /* borders */",
        css_var("color-border-default", n["800"]),
        css_var("color-border-strong", n["500"]) + f"  /* {pair(n['500'], n['950']):.2f}:1 */",
        css_var("color-border-focus", b["500"]),
        css_var("color-border-error", p["red"]["500"]),
        "",
        "  /* feedback (darkened surfaces, lightened text) */",
        css_var("color-feedback-success-bg", p["green"]["900"]),
        css_var("color-feedback-success-text", p["green"]["300"]),
        css_var("color-feedback-warning-bg", p["amber"]["900"]),
        css_var("color-feedback-warning-text", p["amber"]["300"]),
        css_var("color-feedback-error-bg", p["red"]["900"]),
        css_var("color-feedback-error-text", p["red"]["400"]),
        css_var("color-feedback-info-bg", b["900"]),
        css_var("color-feedback-info-text", b["300"]),
        "",
        "  /* interactive */",
        css_var("color-interactive-hover", "rgba(255, 255, 255, 0.06)"),
        css_var("color-interactive-active", "rgba(255, 255, 255, 0.10)"),
        css_var("color-interactive-selected-bg", b["900"]),
        css_var("color-interactive-selected-border", b["700"]),
        css_var("color-scrim", "rgba(0, 0, 0, 0.7)"),
        css_var("shadow-focus-ring", f"0 0 0 2px {n['950']}, 0 0 0 4px {b['500']}"),
        "}",
        "",
        "@media (prefers-reduced-motion: reduce) {",
        "  :root { --transition-micro: 0ms; }",
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    palette = build()
    doc = build_colors_json(palette)
    (OUT_DIR / "colors.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")

    theme = build_theme_css(palette)
    (ROOT / "web" / "src" / "styles" / "theme.css").write_text(theme)

    print(f"wrote {OUT_DIR / 'colors.json'}")
    print(f"wrote {ROOT / 'web' / 'src' / 'styles' / 'theme.css'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
