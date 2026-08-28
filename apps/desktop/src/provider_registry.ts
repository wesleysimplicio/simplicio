import type { DesktopSnapshot, ProviderConnection, ProviderState } from "./contracts";

export const PROVIDER_STATES: readonly ProviderState[] = [
  "connected",
  "registered",
  "detected",
  "needs_attention",
  "not_installed",
];

const stateRank: Record<ProviderState, number> = {
  connected: 0,
  needs_attention: 1,
  registered: 2,
  detected: 3,
  not_installed: 4,
};

/** Derives the UI state from evidence, never from a host's display label. */
export function canonicalProviderState(provider: ProviderConnection): ProviderState {
  if (provider.installState === "absent") return "not_installed";

  if (
    provider.registrationState === "registered" &&
    provider.handshakeState === "live" &&
    provider.freshness === "current"
  ) {
    return "connected";
  }

  if (
    provider.handshakeState === "stale" ||
    provider.freshness === "stale" ||
    /drift|incompat|failed/i.test(provider.reasonCode)
  ) {
    return "needs_attention";
  }

  if (provider.registrationState === "registered") return "registered";
  return "detected";
}

export function normalizeProvider(provider: ProviderConnection): ProviderConnection {
  return { ...provider, state: canonicalProviderState(provider) };
}

export function providerRegistry(providers: ProviderConnection[]): ProviderConnection[] {
  return providers
    .map(normalizeProvider)
    .sort((left, right) => stateRank[left.state] - stateRank[right.state] || left.name.localeCompare(right.name));
}

export interface RedactedProviderScan {
  id: string;
  name: string;
  state: ProviderState;
  installState: ProviderConnection["installState"];
  registrationState: ProviderConnection["registrationState"];
  handshakeState: ProviderConnection["handshakeState"];
  freshness: ProviderConnection["freshness"];
  reasonCode: string;
  availableActions: ProviderConnection["availableActions"];
}

/** Bounded dry-run data for diagnostics/UI. It intentionally omits detail and config bodies. */
export function redactedProviderScan(
  snapshot: { providers: DesktopSnapshot["providers"]; limits: { maxProviders: number } },
): RedactedProviderScan[] {
  return providerRegistry(snapshot.providers)
    .slice(0, snapshot.limits.maxProviders)
    .map(({ id, name, state, installState, registrationState, handshakeState, freshness, reasonCode, availableActions }) => ({
      id,
      name,
      state,
      installState,
      registrationState,
      handshakeState,
      freshness,
      reasonCode,
      availableActions,
    }));
}
