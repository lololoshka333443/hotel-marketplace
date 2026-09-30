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

from gen_palette import build, contrast

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "web" / "src" / "styles" / "tokens"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def color(value: str, description: str = "") -> dict:
    out: dict = {"$type": "color", "$value": value}
    if description:
        out["$description"] = description
    return out


def build_colors_json(p: dict) -> dict:
    def c(key: str, description: str = "") -> dict:
        return color(p[key], description)

    primitive = {
        "paper": c("paper", "The page — warm parchment, never pure white"),
        "surface": c("surface", "Cards and inputs"),
        "ink": c("ink", "Type and the primary button"),
        "ink-soft": c("ink_soft", "Secondary type, eyebrows"),
        "muted": c("muted", "Control boundaries, disabled type"),
        "line": c("line", "Decorative hairlines — no contrast role"),
        "line-strong": c("line_strong", "A stronger decorative hairline"),
        "wash": c("wash", "Hover, sunken surfaces, disabled fill"),
        "danger": c("danger", "The one accent, and it is rare"),
        "success-text": c("success_text"),
        "success-bg": c("success_bg"),
        "warning-text": c("warning_text"),
        "warning-bg": c("warning_bg"),
    }

    def pair(fg: str, bg: str) -> float:
        return contrast(fg, bg)

    doc = {
        "$schema": "https://design-tokens.github.io/community-group/format/",
        "$description": (
            "Hotel marketplace tokens — paper and ink: warm parchment page, "
            "near-black type, almost no accent. Every semantic pair is verified "
            "WCAG 2.2 (4.5:1 text, 3:1 UI) by scripts/gen_palette.py. Light only: "
            "the mood is a printed city guide, not a dashboard."
        ),
        "primitive": {
            "$description": "The chosen few — never reference directly in components",
            **primitive,
        },
        "semantic": {
            "$description": "Purpose-based tokens — use these in design and code",
            "action": {
                "primary": c("ink", f"ink; button-text on it {pair(p['button_text'], p['ink']):.2f}:1"),
                "primary-hover": c("button_hover", "ink warmed a step"),
                "primary-active": c("button_active"),
                "secondary": color("transparent", "Outline button: border + ink type"),
                "secondary-hover": c("wash", "The border stays; the fill washes"),
                "destructive": c("danger", "Rare — destructive only"),
                "destructive-hover": c("danger_hover"),
            },
            "feedback": {
                "success-bg": c("success_bg"),
                "success-text": c("success_text"),
                "warning-bg": c("warning_bg"),
                "warning-text": c("warning_text"),
                "error-bg": c("error_bg"),
                "error-text": c("error_text"),
                "info-bg": c("info_bg"),
                "info-text": c("info_text"),
            },
            "text": {
                "primary": c("ink", f"{pair(p['ink'], p['paper']):.2f}:1 on paper"),
                "secondary": c("ink_soft", f"{pair(p['ink_soft'], p['paper']):.2f}:1 on paper"),
                # Not a chosen color: derived to the AA floor, because fine print
                # and placeholders are text and 3.4:1 is not text.
                "tertiary": c(
                    "tertiary",
                    f"derived: muted darkened to 4.5:1 on paper ({pair(p['tertiary'], p['paper']):.2f}:1)",
                ),
                "disabled": c("muted", "exempt from 4.5:1 — disabled, not content"),
                "on-action": c("button_text", f"{pair(p['button_text'], p['ink']):.2f}:1 on ink"),
                "link": c("ink", "ink, not an accent — affordance comes from the underline"),
                "link-hover": c("ink_soft"),
            },
            "surface": {
                "page": c("paper"),
                "card": c("surface"),
                "raised": c("surface"),
                "sunken": c("wash"),
                "overlay": c("scrim", "Modal/drawer backdrop"),
                "disabled": c("wash"),
            },
            "border": {
                "default": c("line", "hairline — cards, dividers; no contrast role"),
                "strong": c("muted", f"control boundary, {pair(p['muted'], p['paper']):.2f}:1 (3:1 UI)"),
                "focus": c("ink", "Focus turns the border ink, not blue"),
                "error": c("danger"),
            },
            "interactive": {
                "hover-overlay": c("wash", "Hover shifts to wash, nothing else moves"),
                "active-overlay": c("line_strong"),
                "selected-bg": c("wash"),
                "selected-border": c("muted"),
            },
        },
        "component": {
            "$description": "Component-scoped tokens — use in component code",
            "button": {
                "primary-bg": {"$type": "color", "$value": "{semantic.action.primary}"},
                "primary-bg-hover": {"$type": "color", "$value": "{semantic.action.primary-hover}"},
                "primary-bg-active": {"$type": "color", "$value": "{semantic.action.primary-active}"},
                "primary-text": {"$type": "color", "$value": "{semantic.text.on-action}"},
                "secondary-bg": {"$type": "color", "$value": "{semantic.action.secondary}"},
                "secondary-bg-hover": {"$type": "color", "$value": "{semantic.action.secondary-hover}"},
                "secondary-text": {"$type": "color", "$value": "{semantic.text.primary}"},
                "tertiary-text": {"$type": "color", "$value": "{semantic.text.primary}"},
                "ghost-bg": color("transparent"),
                "ghost-bg-hover": {"$type": "color", "$value": "{semantic.interactive.hover-overlay}"},
                "ghost-text": {"$type": "color", "$value": "{semantic.text.primary}"},
                "destructive-bg": {"$type": "color", "$value": "{semantic.action.destructive}"},
                "destructive-bg-hover": {"$type": "color", "$value": "{semantic.action.destructive-hover}"},
                "destructive-text": {"$type": "color", "$value": "{semantic.text.on-action}"},
                "disabled-bg": {"$type": "color", "$value": "{semantic.surface.disabled}"},
                "disabled-text": {"$type": "color", "$value": "{semantic.text.disabled}"},
            },
            "input": {
                "bg": {"$type": "color", "$value": "{semantic.surface.card}"},
                "bg-disabled": {"$type": "color", "$value": "{semantic.surface.disabled}"},
                "border": {"$type": "color", "$value": "{semantic.border.strong}"},
                "border-focus": {"$type": "color", "$value": "{semantic.border.focus}"},
                "border-error": {"$type": "color", "$value": "{semantic.border.error}"},
                "text": {"$type": "color", "$value": "{semantic.text.primary}"},
                "placeholder": {"$type": "color", "$value": "{semantic.text.tertiary}"},
            },
            "card": {
                "bg": {"$type": "color", "$value": "{semantic.surface.card}"},
                "border": {"$type": "color", "$value": "{semantic.border.default}"},
            },
        },
    }
    return doc


def css_var(name: str, value: str) -> str:
    return f"  --{name}: {value};"


def build_theme_css(p: dict) -> str:
    def pair(fg: str, bg: str) -> float:
        return contrast(fg, bg)

    lines = [
        "/* theme.css — the ONE shared token theme. Import this once at the app root.",
        " * Every page/component references these variables; none defines its own colors.",
        " * Generated by scripts/emit_tokens.py from scripts/gen_palette.py.",
        " * Contrast values are measured, not eyeballed (coloraide, WCAG 2.2).",
        " *",
        " * Paper and ink: a warm parchment page, near-black type, almost no accent.",
        " * Light only — the mood is a printed city guide, not a dashboard. Raw values",
        " * live here as --t-*; src/styles/index.css aliases them into Tailwind v4's",
        " * @theme namespaces so utilities like bg-action-primary generate. */",
        "",
        ":root {",
        "  /* type — a neutral grotesque for UI, an editorial serif for display.",
        "   * JetBrains Mono stays for technical identifiers only (booking codes,",
        "   * API keys, dates): a functional monospace, never a display face. */",
        css_var("t-font-sans", 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'),
        css_var("t-font-serif", '"Spectral", Georgia, "Times New Roman", serif'),
        css_var("t-font-mono", '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
        "",
        "  /* surfaces */",
        css_var("t-surface-page", p["paper"]),
        css_var("t-surface-card", p["surface"]),
        css_var("t-surface-raised", p["surface"]),
        css_var("t-surface-sunken", p["wash"]),
        css_var("t-surface-disabled", p["wash"]),
        css_var("t-surface-overlay", p["scrim"]),
        "",
        "  /* text — dark type is graded against paper, the darker floor */",
        css_var("t-text-primary", p["ink"]) + f"  /* {pair(p['ink'], p['paper']):.2f}:1 */",
        css_var("t-text-secondary", p["ink_soft"]) + f"  /* {pair(p['ink_soft'], p['paper']):.2f}:1 */",
        css_var("t-text-tertiary", p["tertiary"]) + f"  /* {pair(p['tertiary'], p['paper']):.2f}:1, derived */",
        css_var("t-text-disabled", p["muted"]),
        css_var("t-text-on-action", p["button_text"]) + f"  /* {pair(p['button_text'], p['ink']):.2f}:1 on ink */",
        css_var("t-text-link", p["ink"]),
        css_var("t-text-link-hover", p["ink_soft"]),
        "",
        "  /* action */",
        css_var("t-action-primary", p["ink"]),
        css_var("t-action-primary-hover", p["button_hover"]),
        css_var("t-action-primary-active", p["button_active"]),
        css_var("t-action-secondary", "transparent"),
        css_var("t-action-secondary-hover", p["wash"]),
        css_var("t-action-destructive", p["danger"]),
        css_var("t-action-destructive-hover", p["danger_hover"]),
        "",
        "  /* borders */",
        css_var("t-border-default", p["line"]) + "  /* hairline */",
        css_var("t-border-strong", p["muted"]) + f"  /* {pair(p['muted'], p['paper']):.2f}:1, control boundary */",
        css_var("t-border-focus", p["ink"]),
        css_var("t-border-error", p["danger"]),
        "",
        "  /* feedback — muted moss and ochre, never a SaaS palette */",
        css_var("t-feedback-success-bg", p["success_bg"]),
        css_var("t-feedback-success-text", p["success_text"]),
        css_var("t-feedback-warning-bg", p["warning_bg"]),
        css_var("t-feedback-warning-text", p["warning_text"]),
        css_var("t-feedback-error-bg", p["error_bg"]),
        css_var("t-feedback-error-text", p["error_text"]),
        css_var("t-feedback-info-bg", p["info_bg"]),
        css_var("t-feedback-info-text", p["info_text"]),
        "",
        "  /* interactive */",
        css_var("t-interactive-hover", p["wash"]),
        css_var("t-interactive-active", p["line_strong"]),
        css_var("t-interactive-selected-bg", p["wash"]),
        css_var("t-interactive-selected-border", p["muted"]),
        css_var("t-scrim", p["scrim"]),
        "",
        "  /* focus: an ink hairline — no glow, no blue ring. The white inner ring",
        "   * keeps it visible on the ink button too. */",
        css_var(
            "t-shadow-focus-ring",
            f"0 0 0 2px {p['surface']}, 0 0 0 4px {p['ink']}",
        ),
        "",
        "  /* type — the scale, plus the display face's own measure. Body is 17px,",
        "   * lines 1.6; the serif display goes as large as the viewport allows. */",
        css_var("t-text-xs", "0.75rem"),
        css_var("t-text-sm", "0.8125rem"),
        css_var("t-text-base", "1.0625rem"),
        css_var("t-text-lg", "1.1875rem"),
        css_var("t-text-xl", "1.375rem"),
        css_var("t-text-2xl", "1.625rem"),
        css_var("t-text-3xl", "2rem"),
        css_var("t-text-4xl", "2.5rem"),
        css_var("t-text-display", "clamp(2.5rem, 5.5vw, 4.75rem)"),
        css_var("t-leading-tight", "1.25"),
        css_var("t-leading-normal", "1.6"),
        css_var("t-leading-display", "1.08"),
        css_var("t-tracking-tight", "-0.02em"),
        css_var("t-tracking-eyebrow", "0.08em"),
        "",
        "  /* spacing — 4px base scale */",
        css_var("t-space-1", "0.25rem"),
        css_var("t-space-2", "0.5rem"),
        css_var("t-space-3", "0.75rem"),
        css_var("t-space-4", "1rem"),
        css_var("t-space-5", "1.25rem"),
        css_var("t-space-6", "1.5rem"),
        css_var("t-space-8", "2rem"),
        css_var("t-space-10", "2.5rem"),
        css_var("t-space-12", "3rem"),
        css_var("t-space-16", "4rem"),
        css_var("t-space-20", "5rem"),
        css_var("t-space-24", "6rem"),
        "",
        "  /* radius — pills, cards, fields. Nothing else exists. */",
        css_var("t-radius-sm", "0.875rem"),
        css_var("t-radius-button", "999px"),
        css_var("t-radius-lg", "0.875rem"),
        css_var("t-radius-xl", "1.25rem"),
        css_var("t-radius-full", "9999px"),
        "",
        "  /* sizing — the brief's two control heights: buttons 48, fields 52 */",
        css_var("t-size-control-sm", "2.5rem"),
        css_var("t-size-control-md", "2.75rem"),
        css_var("t-size-control-lg", "3rem"),
        css_var("t-size-control-field", "3.25rem"),
        css_var("t-opacity-disabled", "1"),
        css_var("t-transition-micro", "180ms ease-out"),
        css_var("t-duration-micro", "180ms"),
        css_var(
            "t-shadow-overlay",
            "0 2px 10px rgba(28, 25, 22, 0.06)",
        ),
        css_var("t-z-modal", "50"),
        "",
        "  /* native controls + scrollbars follow the theme */",
        "  color-scheme: light;",
        "  /* breakpoints (mobile-first) */",
        css_var("t-bp-sm", "640px"),
        css_var("t-bp-md", "768px"),
        css_var("t-bp-lg", "1024px"),
        css_var("t-bp-xl", "1280px"),
        css_var("t-bp-2xl", "1536px"),
        "}",
        "",
        "@media (prefers-reduced-motion: reduce) {",
        "  :root { --t-transition-micro: 0ms; }",
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
