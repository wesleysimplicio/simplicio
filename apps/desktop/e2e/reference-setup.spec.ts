import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { hostPluginPlan, hostPluginReceipt } from "./host-plugin-fixtures";

type ReferenceSetupWindow = Window & {
  __referenceApplyCount: number;
  __completeReferenceApply?: () => void;
};

test("guided setup keeps progress and consent-controlled actions visible in a short window (mocked IPC)", async ({ page }, testInfo) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  delete snapshot.hostPlugins;
  const plan = hostPluginPlan();
  const operation = hostPluginReceipt();
  await page.addInitScript(({ snapshot, plan, operation }) => {
    Object.assign(window, { __referenceApplyCount: 0, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return plan;
        if (command === "desktop_apply_host_plugins") {
          const current = window as ReferenceSetupWindow;
          current.__referenceApplyCount++;
          await new Promise<void>((resolve) => { current.__completeReferenceApply = resolve; });
          return operation;
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_setup_command";
      },
    } });
  }, { snapshot, plan, operation });
  await page.setViewportSize({ width: 960, height: 600 });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  const apply = page.getByRole("button", { name: "Instalar e conectar", exact: true });
  const progress = page.getByRole("progressbar");
  await expect(apply).toBeInViewport();
  await expect(progress).toBeInViewport();
  await expect(apply).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Tudo pronto para revisar." })).toBeFocused();
  expect(await page.evaluate(() => (window as ReferenceSetupWindow).__referenceApplyCount)).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("setup-review.png") });

  const review = page.getByRole("button", { name: "Revisar destinos", exact: true });
  await expect(review).toBeInViewport();
  await review.click();
  await expect(page.getByRole("heading", { name: "O que será configurado", exact: true })).toBeInViewport();
  await expect(page.getByRole("heading", { name: "O que será configurado", exact: true })).toBeFocused();
  await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
  await expect(apply).toBeDisabled();
  expect(await page.evaluate(() => (window as ReferenceSetupWindow).__referenceApplyCount)).toBe(0);
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await expect(progress).toBeInViewport();
  await expect(apply).toBeInViewport();
  await apply.click();
  await expect(page.getByRole("heading", { name: "Configurando o Simplicio…" })).toBeVisible();
  await expect(progress).toHaveAttribute("value", "2");
  await expect(page.getByRole("button", { name: "Voltar ao app", exact: true })).toBeDisabled();
  const details = page.getByRole("button", { name: "Mostrar detalhes", exact: true });
  await expect(details).toBeInViewport();
  await details.click();
  await expect(page.getByRole("region", { name: "Detalhes da configuração", exact: true })).toBeInViewport();
  await expect(progress).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath("setup-running.png") });

  await page.evaluate(() => (window as ReferenceSetupWindow).__completeReferenceApply?.());
  await expect(page.getByRole("heading", { name: "Configuração concluída" })).toBeFocused();
  await expect(progress).toHaveAttribute("value", "4");
  await expect(page.getByRole("button", { name: "Abrir Simplicio", exact: true })).toBeInViewport();
  expect(await page.evaluate(() => (window as ReferenceSetupWindow).__referenceApplyCount)).toBe(1);
});
