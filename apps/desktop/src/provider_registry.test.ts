import { describe, expect, it } from "vitest";
import { createDemoSnapshot } from "./demo";
import { canonicalProviderState, providerRegistry, redactedProviderScan } from "./provider_registry";

describe("canonical provider registry", () => {
  it("requires current handshake evidence before showing connected", () => {
    const provider = createDemoSnapshot("active").providers[0];
    expect(canonicalProviderState(provider)).toBe("detected");
    expect(canonicalProviderState({ ...provider, registrationState: "registered" })).toBe("registered");
    expect(canonicalProviderState({ ...provider, registrationState: "registered", handshakeState: "live" })).toBe("connected");
  });

  it("maps stale or drifted evidence to attention and preserves absent hosts", () => {
    const [provider] = createDemoSnapshot("active").providers;
    expect(canonicalProviderState({ ...provider, freshness: "stale" })).toBe("needs_attention");
    expect(canonicalProviderState({ ...provider, reasonCode: "config_drift" })).toBe("needs_attention");
    expect(canonicalProviderState({ ...provider, installState: "absent" })).toBe("not_installed");
  });

  it("sorts the five states and returns a bounded redacted scan", () => {
    const snapshot = createDemoSnapshot("active");
    const registry = providerRegistry(snapshot.providers);
    expect(registry.map((provider) => provider.state)).toEqual([
      "needs_attention", "needs_attention", "needs_attention", "detected", "detected", "detected", "not_installed", "not_installed", "not_installed", "not_installed", "not_installed", "not_installed", "not_installed", "not_installed",
    ]);
    const bounded = { ...snapshot, limits: { ...snapshot.limits, maxProviders: 3 } };
    const scan = redactedProviderScan(bounded);
    expect(scan).toHaveLength(3);
    expect(scan[0]).not.toHaveProperty("detail");
    expect(JSON.stringify(scan)).not.toContain("config");
  });
});
