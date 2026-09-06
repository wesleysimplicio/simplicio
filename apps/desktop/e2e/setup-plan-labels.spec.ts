import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { hostPluginPlan } from "./host-plugin-fixtures";

test("guided setup labels all eight Runtime host dispositions without inventing native providers (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  delete snapshot.hostPlugins;
  const plan = hostPluginPlan();
  plan.plan.hosts[0] = { ...plan.plan.hosts[0], mode: "manager", disposition: "ready", reason_code: "ready" };
  plan.plan.hosts[1] = { ...plan.plan.hosts[1], disposition: "already_exact", reason_code: "already_exact" };
  plan.plan.hosts[2] = { ...plan.plan.hosts[2], disposition: "not_detected", reason_code: "not_detected" };
  plan.plan.hosts[3] = { ...plan.plan.hosts[3], disposition: "unknown", reason_code: "unknown" };
  plan.plan.hosts[4] = { ...plan.plan.hosts[4], disposition: "blocked", reason_code: "local_install_capability_unverified" };
  await page.addInitScript(({ snapshot, plan }) => {
    Object.assign(window, { __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
          if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
          if (command === "desktop_preparation_status") return true;
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return plan;
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_setup_labels_command";
      },
    } });
  }, { snapshot, plan });

  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Install Now", exact: true }).click();
  const planRegion = page.getByRole("region", { name: "Plano de instalação", exact: true });
  for (const [label, status] of [
    ["Codex", "Pronto para configurar"],
    ["Claude Code", "Já atualizado"],
    ["Gemini CLI", "Aplicativo não detectado"],
    ["GitHub Copilot", "Estado não confirmado"],
    ["Qwen Code", "Instalação manual"],
  ]) {
    await expect(planRegion.getByRole("listitem").filter({ has: page.getByText(label, { exact: true }) })).toContainText(status);
  }
  await expect(planRegion.getByRole("listitem")).toHaveCount(8);
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
});
