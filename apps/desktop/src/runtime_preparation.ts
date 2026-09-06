/** A preview is not an installation receipt and cannot unlock sign-in. */
export type PreparationPlan = {
  schema: "simplicio.desktop-preparation-plan/v1";
  status: "planned";
  configurationWrites: number;
  effectsApplied: false;
  memoryReady: false;
  requiresApply: true;
  python: {
    status: "detected" | "unavailable" | "not_detected";
    version?: string;
    dependenciesVerified: false;
  };
};

export function parsePreparationPlan(raw: unknown): PreparationPlan {
  const invalid = () => new Error("preparation_plan_invalid");
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw invalid();
  const value = raw as Record<string, unknown>;
  if (value.schema !== "simplicio.desktop-preparation-plan/v1" ||
      value.status !== "planned" || value.effectsApplied !== false ||
      value.memoryReady !== false || value.requiresApply !== true ||
      !Number.isInteger(value.configurationWrites) ||
      (value.configurationWrites as number) < 0 || (value.configurationWrites as number) > 64) throw invalid();
  if (!value.python || typeof value.python !== "object" || Array.isArray(value.python)) throw invalid();
  const python = value.python as Record<string, unknown>;
  if (!["detected", "unavailable", "not_detected"].includes(String(python.status)) ||
      python.dependenciesVerified !== false) throw invalid();
  if (python.status === "detected" &&
      (typeof python.version !== "string" || !/^3\.[0-9]{1,3}\.[0-9]{1,3}$/.test(python.version))) throw invalid();
  return {
    schema: "simplicio.desktop-preparation-plan/v1", status: "planned",
    configurationWrites: value.configurationWrites as number,
    effectsApplied: false, memoryReady: false, requiresApply: true,
    python: {
      status: python.status as PreparationPlan["python"]["status"],
      ...(python.status === "detected" ? { version: python.version as string } : {}),
      dependenciesVerified: false,
    },
  };
}
