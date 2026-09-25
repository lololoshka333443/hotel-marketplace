import { useEffect, useState } from "react";

/**
 * Countdown to a deadline (ISO string). Returns ms left, or null when expired
 * or unset. Used for the booking hold TTL (15 min) so the guest sees exactly
 * how long the price is guaranteed before they pay.
 */
export function useCountdown(deadline: string | null | undefined): number | null {
  const [left, setLeft] = useState<number | null>(compute(deadline));

  useEffect(() => {
    setLeft(compute(deadline));
    if (!deadline) return;

    const tick = () => setLeft(compute(deadline));
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [deadline]);

  return left;
}

function compute(deadline: string | null | undefined): number | null {
  if (!deadline) return null;
  const ms = Date.parse(deadline) - Date.now();
  return Number.isFinite(ms) ? Math.max(0, ms) : null;
}

export function formatCountdown(ms: number | null): string {
  if (ms === null) return "--:--";
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
