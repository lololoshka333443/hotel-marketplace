/**
 * Money and dates for the guest-facing UI.
 *
 * The backend keeps `currency` per property (ISO 4217, RUB by default), so the
 * formatter takes it rather than assuming ₽. Values travel as plain numbers —
 * the API rounds to kopecks but never sends strings.
 */

const CURRENCY_SYMBOL: Record<string, string> = {
  RUB: "₽",
  USD: "$",
  EUR: "€",
};

/**
 * A night price, e.g. `7 200 ₽`. Grouping is the readable part; the fraction
 * is noise for a per-night rate and the rest of the UI already drops it.
 */
export function formatPrice(value: number, currency = "RUB"): string {
  const rounded = Math.round(value);
  const grouped = rounded.toLocaleString("ru-RU");
  const symbol = CURRENCY_SYMBOL[currency] ?? currency;
  return `${grouped} ${symbol}`;
}

/** Sentence form: `от 7 200 ₽ за ночь` — the catalog card's price line. */
export function formatPriceFrom(value: number, currency = "RUB"): string {
  return `от ${formatPrice(value, currency)} за ночь`;
}
