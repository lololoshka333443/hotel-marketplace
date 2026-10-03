/**
 * Cancellation policy wording for the guest.
 *
 * The backend stores the rate plan's policy as a machine code, but the refund
 * path applies one legal deadline to every booking (see
 * app.config.legal.CANCELLATION_FREE_BEFORE_HOURS). The 'moderate' and
 * 'strict' codes have no matching rule in the code yet, so this map only
 * labels the policy the money actually follows — inventing a deadline the
 * refund does not honour would promise a guest money we keep.
 *
 * A room whose partner never set a rate plan has no terms: say so plainly
 * instead of defaulting to the most forgiving policy.
 */

export function policyLabel(code: string | null | undefined): string {
  if (!code) return "Условия отмены не указаны";
  if (code === "flexible") {
    return "Бесплатная отмена за сутки до заезда";
  }
  return "Условия отмены уточняйте";
}
