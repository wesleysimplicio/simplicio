import { describe, expect, it } from "vitest";
import { activityMatchesSearch, redactedActivity } from "./screens/ActivityScreen";
import type { ActivityItem } from "./contracts";

const item: ActivityItem = {
  id: "event-1",
  title: "Model turn",
  detail: "Redacted",
  provider: "openai",
  savedTokens: 42,
  occurredAt: "2026-09-02T00:00:00Z",
  status: "verified",
};

describe("Activity savings proof", () => {
  it("does not export a savings number without a proof class", () => {
    expect(redactedActivity([item])).toEqual([{
      id: "event-1", title: "Model turn", provider: "openai",
      savedTokens: null, occurredAt: item.occurredAt, status: "verified",
    }]);
  });

  it("keeps the value only when the caller has a Runtime proof class", () => {
    expect(redactedActivity([item], true)[0].savedTokens).toBe(42);
  });

  it("searches receipt title, detail and provider without accent sensitivity", () => {
    expect(activityMatchesSearch({ ...item, title: "Validação determinística" }, "validacao")).toBe(true);
    expect(activityMatchesSearch({ ...item, detail: "Recibo do Runtime" }, "runtime")).toBe(true);
    expect(activityMatchesSearch(item, "grok")).toBe(false);
  });
});
