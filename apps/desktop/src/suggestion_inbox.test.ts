import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createSuggestionInboxProjection } from "./suggestion_inbox";

describe("suggestions.inbox/v1", () => {
  it("keeps suggestions review-only in preview", () => {
    const inbox = createSuggestionInboxProjection(createDemoSnapshot("active"));
    expect(inbox.schema).toBe("suggestions.inbox/v1");
    expect(inbox.suggestions.every((item) => item.state === "review_required")).toBe(true);
    expect(inbox.actions).toEqual({ accept: false, dismiss: false, snooze: false });
  });
});
