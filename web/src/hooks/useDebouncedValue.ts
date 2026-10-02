import { useEffect, useState } from "react";

/**
 * Delay a fast-changing value until it settles, so typing into a search box
 * fires one server query per pause instead of one per keystroke. The pending
 * keystrokes are not wanted — only the value the user stopped on.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
