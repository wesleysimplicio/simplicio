const UNAVAILABLE = "Data não informada.";
const UNIX = /^unix:(0|[1-9]\d{0,12})$/;
const ISO = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(?:Z|([+-])(\d{2}):(\d{2})))?$/;

/** Display supported Runtime timestamps only; malformed metadata is never echoed. */
export function formatRuntimeTimestamp(value: unknown, options: { fallback?: string; timeZone?: string } = {}): string {
  const unavailable = options.fallback ?? UNAVAILABLE;
  if (typeof value !== "string" || value.length > 64) return unavailable;
  const unix = UNIX.exec(value);
  const iso = unix ? null : ISO.exec(value);
  if (!unix && !iso) return unavailable;
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]);
    const day = Number(iso[3]);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (month < 1 || month > 12 || day < 1 || day > days[month - 1]
      || Number(iso[4] ?? 0) > 23 || Number(iso[5] ?? 0) > 59 || Number(iso[6] ?? 0) > 59
      || Number(iso[8] ?? 0) > 23 || Number(iso[9] ?? 0) > 59) return unavailable;
  }
  const milliseconds = unix ? Number(unix[1]) * 1000 : Date.parse(value);
  if (!Number.isSafeInteger(milliseconds) || Math.abs(milliseconds) > 8_640_000_000_000_000) return unavailable;
  const dateOnly = iso !== null && iso[4] === undefined;
  try {
    // A date-only expiry is a calendar date, not midnight in the user's timezone.
    return new Intl.DateTimeFormat("pt-BR", dateOnly
      ? { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "UTC" }
      : { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: options.timeZone }
    ).format(new Date(milliseconds));
  } catch { return unavailable; }
}
