export type PreparationResult = {
  schema: "simplicio.desktop-preparation-result/v1";
  status: "ready";
  effectsApplied: true;
  runtimeDependencies: { status: "ready"; pythonRequired: false };
  python: {
    status: "detected" | "unavailable" | "not_detected";
    version?: string;
    dependenciesVerified: false;
  };
  memory: { ready: true; items: number; skills: number; migrations: number };
  clients: { configured: number; skipped: number };
  redacted: true;
};

export function parsePreparationResult(raw: unknown): PreparationResult {
  const invalid = () => new Error("preparation_result_invalid");
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw invalid();
  const value = raw as Record<string, unknown>;
  const runtimeDependencies = value.runtimeDependencies as Record<string, unknown> | undefined;
  const python = value.python as Record<string, unknown> | undefined;
  const memory = value.memory as Record<string, unknown> | undefined;
  const clients = value.clients as Record<string, unknown> | undefined;
  if (value.schema !== "simplicio.desktop-preparation-result/v1"
    || value.status !== "ready" || value.effectsApplied !== true || value.redacted !== true
    || runtimeDependencies?.status !== "ready" || runtimeDependencies.pythonRequired !== false
    || !python || !["detected", "unavailable", "not_detected"].includes(String(python.status))
    || python.dependenciesVerified !== false
    || (python.status === "detected"
      && (typeof python.version !== "string" || !/^3\.[0-9]{1,3}\.[0-9]{1,3}$/.test(python.version)))
    || memory?.ready !== true
    || !Number.isSafeInteger(memory.items) || (memory.items as number) < 100
    || !Number.isSafeInteger(memory.skills) || (memory.skills as number) < 50
    || !Number.isSafeInteger(memory.migrations) || (memory.migrations as number) < 1
    || (memory.migrations as number) > 64
    || !Number.isSafeInteger(clients?.configured) || (clients!.configured as number) < 0
    || (clients!.configured as number) > 64
    || !Number.isSafeInteger(clients?.skipped) || (clients!.skipped as number) < 0
    || (clients!.skipped as number) > 64) {
    throw invalid();
  }
  return {
    schema: "simplicio.desktop-preparation-result/v1",
    status: "ready",
    effectsApplied: true,
    runtimeDependencies: { status: "ready", pythonRequired: false },
    python: {
      status: python.status as PreparationResult["python"]["status"],
      ...(python.status === "detected" ? { version: python.version as string } : {}),
      dependenciesVerified: false,
    },
    memory: {
      ready: true,
      items: memory.items as number,
      skills: memory.skills as number,
      migrations: memory.migrations as number,
    },
    clients: {
      configured: clients!.configured as number,
      skipped: clients!.skipped as number,
    },
    redacted: true,
  };
}
