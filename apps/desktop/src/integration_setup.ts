export interface IntegrationPlan {
  schema: "simplicio.desktop-integration-plan/v1";
  source: "runtime" | "preview";
  planDigest: string;
  changes: Array<{ label: string; changed: boolean; exists: boolean }>;
}

export function integrationChangeLabel(change: IntegrationPlan["changes"][number]): string {
  if (change.changed) return change.exists ? "Atualizar" : "Criar";
  return change.exists ? "Já configurado" : "Configuração ausente";
}

export function parseIntegrationPlan(value: unknown): IntegrationPlan {
  if (!value || typeof value !== "object") throw new Error("integration_plan_invalid");
  const plan = value as Record<string, unknown>;
  if (plan.schema !== "simplicio.desktop-integration-plan/v1" || !["runtime", "preview"].includes(String(plan.source))
    || typeof plan.planDigest !== "string" || !/^sha256:[a-f0-9]{64}$/.test(plan.planDigest)
    || !Array.isArray(plan.changes) || plan.changes.length > 64) throw new Error("integration_plan_invalid");
  const changes = plan.changes.map((value: unknown) => {
    if (!value || typeof value !== "object") throw new Error("integration_plan_invalid");
    const row = value as Record<string, unknown>;
    if (typeof row.label !== "string" || !/^[a-zA-Z0-9._-]{1,128}$/.test(row.label)
      || typeof row.changed !== "boolean" || typeof row.exists !== "boolean") throw new Error("integration_plan_invalid");
    return { label: row.label, changed: row.changed, exists: row.exists };
  });
  if (new Set(changes.map((row) => row.label)).size !== changes.length) {
    throw new Error("integration_plan_ambiguous_targets");
  }
  return { schema: "simplicio.desktop-integration-plan/v1", source: plan.source as IntegrationPlan["source"], planDigest: plan.planDigest, changes };
}

/** Recheck existing or changed reviewed targets, never newly discovered clients or handshakes. */
export function integrationTargetsVerified(reviewed: IntegrationPlan, observed: IntegrationPlan): boolean {
  if (reviewed.source !== observed.source
    || new Set(reviewed.changes.map((row) => row.label)).size !== reviewed.changes.length
    || new Set(observed.changes.map((row) => row.label)).size !== observed.changes.length) return false;
  for (const target of reviewed.changes.filter((row) => row.exists || row.changed)) {
    const current = observed.changes.find((row) => row.label === target.label);
    if (!current || !current.exists || current.changed) return false;
  }
  return true;
}
