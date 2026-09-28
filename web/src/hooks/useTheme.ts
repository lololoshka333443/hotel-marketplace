import { useCallback, useEffect, useState } from "react";

/**
 * Explicit light/dark switch (WCAG 1.4.11 context, and plain comfort).
 *
 * theme.css swaps the `--t-*` tokens under `[data-theme="dark"]`, and falls
 * back to `prefers-color-scheme` when no attribute is set. This hook owns that
 * attribute: the OS preference is the default until the user picks, then their
 * choice wins and survives a reload.
 */

const STORAGE_KEY = "theme";
const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

function stored(): Theme | null {
  const value = localStorage.getItem(STORAGE_KEY);
  return THEMES.includes(value as Theme) ? (value as Theme) : null;
}

function apply(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document === "undefined") return "light";
    const explicit = document.documentElement.getAttribute("data-theme");
    return THEMES.includes(explicit as Theme) ? (explicit as Theme) : "light";
  });

  // An inline script in index.html sets the attribute before paint, so this
  // only has work to do after a user action.
  useEffect(() => {
    apply(theme);
  }, [theme]);

  // The user has not picked yet: follow the OS, and keep following it.
  useEffect(() => {
    if (stored() !== null) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = (event: MediaQueryListEvent) =>
      setTheme(event.matches ? "dark" : "light");
    media.addEventListener("change", follow);
    setTheme(media.matches ? "dark" : "light");
    return () => media.removeEventListener("change", follow);
  }, []);

  const toggle = useCallback(() => {
    setTheme((previous) => {
      const next = previous === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { theme, toggle };
}
