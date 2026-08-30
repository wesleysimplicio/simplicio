export interface IntegrationPlan {
  schema: "simplicio.desktop-integration-plan/v1";
  source: "runtime" | "preview";
  planDigest: string;
  changes: Array<{ label: string; changed: boolean; exists: boolean }>;
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
  return { schema: "simplicio.desktop-integration-plan/v1", source: plan.source as IntegrationPlan["source"], planDigest: plan.planDigest, changes };
}
