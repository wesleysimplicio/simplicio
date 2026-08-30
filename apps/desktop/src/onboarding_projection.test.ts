import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { createOnboardingProjection } from "./onboarding_projection";

describe("onboarding.v1", () => {
  it("offers universal personas in Simple mode without hidden activation", () => {
    const onboarding = createOnboardingProjection(createDemoSnapshot("active"));
    expect(onboarding.schema).toBe("onboarding.v1");
    expect(onboarding.mode).toBe("simple");
    expect(onboarding.templates.map((template) => template.id)).toEqual(["personal", "study", "create", "business", "software", "explore"]);
    expect(onboarding.reviewRequired).toBe(true);
    expect(onboarding.createsProvider).toBe(false);
    expect(onboarding.activatesBot).toBe(false);
    expect(onboarding.submitAvailable).toBe(false);
  });

  it("keeps Advanced as a view mode, not a bypass for Runtime policy", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.source = "runtime";
    const onboarding = createOnboardingProjection(snapshot, "advanced");
    expect(onboarding.mode).toBe("advanced");
    expect(onboarding.submitAvailable).toBe(true);
  });
});
