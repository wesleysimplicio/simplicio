import { describe, expect, it } from "vitest";
import {
  HOST_PLUGIN_IDS,
  createPreviewIntegrationPlan,
  isHostPluginDigest,
  hostPluginOutcomeLabel,
  integrationChangeLabel,
  parseHostPluginOperationResult,
  parseIntegrationPlan,
} from "./integration_setup";

const digest = (value: string) => `sha256:${value.repeat(64)}`;

function runtimePlan() {
  return {
    schema: "simplicio.host-plugin-command-result/v1",
    result: "plan",
    plan: {
      schema: "simplicio.host-plugin-plan-summary/v1",
      plan_digest: digest("a"),
      selection: { scope: "all" },
      manifest_digest: digest("b"),
      plugin_version: "3.8.41",
      component_versions: { simplicio: "3.8.41", secret: "/private/component" },
      hosts: HOST_PLUGIN_IDS.map((host, index) => ({
        host,
        mode: index < 6 ? "manager" : "portable",
        disposition: index === 7 ? "blocked" : index === 6 ? "unknown" : "ready",
        reason_code: index === 7 ? "local_install_capability_unverified" : index === 6 ? "unknown" : "ready",
        manager_path: "/private/bin",
        raw_config: "DO_NOT_LEAK",
      })),
    },
  };
}

function runtimeSnapshot(state: "complete" | "partial" | "requires_reconcile" = "complete") {
  return {
    schema: "simplicio.host-plugin-snapshot/v1",
    receipt_schema: "simplicio.host-plugin-receipt/v1",
    receipt_digest: digest("c"),
    operation: "apply",
    state,
    attempt_id: "private-attempt",
    revision: 2,
    durable_id: digest("d"),
    plan_digest: digest("a"),
    manifest_digest: digest("b"),
    hosts: HOST_PLUGIN_IDS.map((host, index) => ({
      host,
      status: index === 0 ? "applied_unverified" : index === 1 ? "blocked" : "verified",
      reason_code: index === 0 ? "manager_readback_unknown" : index === 1 ? "precondition_blocked" : "exact_readback",
      failure_code: index === 1 ? "manager_unavailable" : undefined,
      verification: index < 2 ? "none" : "installed_tree_and_manager",
      reconcile: null,
      backup_id: "/private/backup",
      stdout: "DO_NOT_LEAK",
    })),
  };
}

describe("Runtime host-plugin plan review", () => {
  it("accepts only opaque SHA-256 identifiers for effect commands", () => {
    expect(isHostPluginDigest(digest("a"))).toBe(true);
    expect(isHostPluginDigest("sha256:private")).toBe(false);
    expect(isHostPluginDigest("/Users/private/receipt")).toBe(false);
  });
  it("requires and shows exactly the eight canonical native/plugin hosts", () => {
    const result = parseIntegrationPlan(runtimePlan());
    expect(result.hosts.map(({ host }) => host)).toEqual(HOST_PLUGIN_IDS);
    expect(result.source).toBe("runtime");
    expect(result.planDigest).toBe(digest("a"));
  });

  it("projects only review-safe fields", () => {
    const result = parseIntegrationPlan(runtimePlan());
    const encoded = JSON.stringify(result);
    expect(encoded).not.toContain("private");
    expect(encoded).not.toContain("DO_NOT_LEAK");
    expect(encoded).not.toContain("component_versions");
    expect(result.hosts[0]).toEqual({ host: "codex", mode: "manager", disposition: "ready", reasonCode: "ready" });
  });

  it("rejects missing, duplicated or invented hosts and a non-all selection", () => {
    const missing = runtimePlan();
    missing.plan.hosts.pop();
    expect(() => parseIntegrationPlan(missing)).toThrow("host_plugin_hosts_invalid");
    const duplicate = runtimePlan();
    duplicate.plan.hosts[7] = { ...duplicate.plan.hosts[0] };
    expect(() => parseIntegrationPlan(duplicate)).toThrow("host_plugin_hosts_invalid");
    const invented = runtimePlan();
    invented.plan.hosts[0].host = "fake" as "codex";
    expect(() => parseIntegrationPlan(invented)).toThrow("host_plugin_contract_invalid");
    const one = runtimePlan();
    one.plan.selection = { scope: "one", host: "codex" } as unknown as { scope: string };
    expect(() => parseIntegrationPlan(one)).toThrow("integration_plan_selection_invalid");
  });

  it("uses honest labels for unsupported and unverified native installs", () => {
    const plan = parseIntegrationPlan(runtimePlan());
    expect(integrationChangeLabel(plan.hosts[0])).toBe("Pronto para configurar");
    expect(integrationChangeLabel(plan.hosts[6])).toBe("Estado não confirmado");
    expect(integrationChangeLabel(plan.hosts[7])).toBe("Instalação manual");
  });

  it("provides the same eight-host shape in browser preview without effects", () => {
    const preview = createPreviewIntegrationPlan();
    expect(preview.source).toBe("preview");
    expect(preview.hosts.map(({ host }) => host)).toEqual(HOST_PLUGIN_IDS);
  });
});

describe("canonical apply and reconcile result", () => {
  it("uses the returned snapshot directly and removes receipt internals", () => {
    const result = parseHostPluginOperationResult({
      schema: "simplicio.host-plugin-command-result/v1",
      result: "receipt",
      receipt: { backup_id: "/private/backup", stdout: "DO_NOT_LEAK" },
      snapshot: runtimeSnapshot(),
    });
    expect(result.snapshot.hosts).toHaveLength(8);
    expect(result.snapshot.hosts[0].status).toBe("applied_unverified");
    expect(result.snapshot.hosts[1].status).toBe("blocked");
    expect(hostPluginOutcomeLabel(result.snapshot)).toBe("Concluído com ações manuais");
    const encoded = JSON.stringify(result);
    expect(encoded).not.toContain("backup");
    expect(encoded).not.toContain("private");
    expect(encoded).not.toContain("DO_NOT_LEAK");
    expect(encoded).not.toContain("attempt");
  });

  it.each(["partial", "requires_reconcile"] as const)("preserves %s and its opaque reconcile id", (state) => {
    const result = parseHostPluginOperationResult({
      schema: "simplicio.host-plugin-command-result/v1", result: "receipt", receipt: {}, snapshot: runtimeSnapshot(state),
    });
    expect(result.snapshot.state).toBe(state);
    expect(result.snapshot.receiptId).toBe(digest("d"));
    expect(hostPluginOutcomeLabel(result.snapshot)).toMatch(/parcial|Reconciliação/);
  });

  it("fails closed when a partial result has no durable id", () => {
    const snapshot = runtimeSnapshot("partial");
    (snapshot as Record<string, unknown>).durable_id = undefined;
    expect(() => parseHostPluginOperationResult({
      schema: "simplicio.host-plugin-command-result/v1", result: "receipt", receipt: {}, snapshot,
    })).toThrow("host_plugin_receipt_id_missing");
  });

  it("binds a terminal receipt to the command that requested it", () => {
    const envelope = {
      schema: "simplicio.host-plugin-command-result/v1", result: "receipt", receipt: {}, snapshot: runtimeSnapshot(),
    };
    expect(parseHostPluginOperationResult(envelope, "apply").snapshot.operation).toBe("apply");
    expect(() => parseHostPluginOperationResult(envelope, "reconcile")).toThrow("host_plugin_operation_mismatch");
    const applying = runtimeSnapshot();
    applying.state = "applying" as "complete";
    expect(() => parseHostPluginOperationResult({ ...envelope, snapshot: applying }, "apply"))
      .toThrow("host_plugin_operation_incomplete");
  });

  it("rejects arbitrary status and failure strings instead of reflecting them", () => {
    for (const field of ["status", "failure_code"] as const) {
      const snapshot = runtimeSnapshot();
      (snapshot.hosts[0] as Record<string, unknown>)[field] = "/private/DO_NOT_LEAK";
      expect(() => parseHostPluginOperationResult({
        schema: "simplicio.host-plugin-command-result/v1", result: "receipt", receipt: {}, snapshot,
      })).toThrow("host_plugin_contract_invalid");
    }
  });
});
