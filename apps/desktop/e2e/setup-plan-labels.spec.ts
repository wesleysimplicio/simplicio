import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

test("guided setup distinguishes absent configuration from an unchanged installed target (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot }) => {
    Object.assign(window, { __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_install_diagnostic") return {
          schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: null,
        };
        if (command === "desktop_plan_integrations") return {
          schema: "simplicio.desktop-integration-plan/v1", source: "runtime",
          planDigest: "sha256:" + "a".repeat(64),
          changes: [
            { label: "absent-client", exists: false, changed: false },
            { label: "installed-client", exists: true, changed: false },
            { label: "new-client", exists: false, changed: true },
            { label: "updated-client", exists: true, changed: true },
          ],
        };
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_setup_labels_command";
      },
    } });
  }, { snapshot });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  const plan = page.getByRole("region", { name: "Plano de instalação", exact: true });
  for (const [label, status] of [
    ["absent-client", "Configuração ausente"], ["installed-client", "Já configurado"],
    ["new-client", "Criar"], ["updated-client", "Atualizar"],
  ]) {
    await expect(plan.getByRole("listitem").filter({ has: page.getByText(label, { exact: true }) })).toContainText(status);
  }
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
});
