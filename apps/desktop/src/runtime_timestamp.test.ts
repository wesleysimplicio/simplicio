import { describe, expect, it } from "vitest";
import { formatRuntimeTimestamp } from "./runtime_timestamp";

describe("Runtime timestamp display", () => {
  it("formats Unix seconds and ISO instants with the same known UTC date", () => {
    expect(formatRuntimeTimestamp("unix:0", { timeZone: "UTC" })).toBe("01/01/1970, 00:00:00");
    for (const timestamp of ["unix:1704067200", "2024-01-01T00:00:00Z", "2024-01-01T03:00:00+03:00", "2024-01-01T00:00:00.000000Z"]) {
      expect(formatRuntimeTimestamp(timestamp, { timeZone: "UTC" })).toBe("01/01/2024, 00:00:00");
    }
  });

  it("preserves date-only calendar dates without inventing or shifting their time", () => {
    expect(formatRuntimeTimestamp("2024-02-29", { timeZone: "America/Sao_Paulo" })).toBe("29/02/2024");
    expect(formatRuntimeTimestamp("2026-09-01", { timeZone: "Pacific/Honolulu" })).toBe("01/09/2026");
  });

  it.each([
    undefined, null, true, 1704067200, {}, [], "", "0", "1704067200", "2024", "01/02/2024",
    "unix:", "unix:-1", "unix:1.5", "unix:01", "unix:9007199254740991", "unix:8640000000001",
    "unix:1704067200 ", "unix:1\n", "2024-01-01T00:00:00", "2024-02-30T00:00:00Z",
    "2023-02-29", "1900-02-29", "2024-00-01", "2024-13-01", "2024-01-00",
    "2024-01-01T24:00:00Z", "2024-01-01T00:60:00Z", "2024-01-01T00:00:60Z",
    "2024-01-01T00:00:00+24:00", "2024-01-01T00:00:00+03:60", "2024-01-01T00:00:00Z\n",
    "private-timestamp@example.test", "x".repeat(1000),
  ])("keeps malformed or unsupported metadata unavailable (%j)", (value) => {
    expect(formatRuntimeTimestamp(value, { timeZone: "UTC" })).toBe("Data não informada.");
  });

  it("uses a caller-owned fallback for absent expiry or unavailable date formatting", () => {
    expect(formatRuntimeTimestamp(null, { fallback: "Validade não informada." })).toBe("Validade não informada.");
    expect(formatRuntimeTimestamp("unix:0", { timeZone: "invalid-time-zone" })).toBe("Data não informada.");
  });
});
