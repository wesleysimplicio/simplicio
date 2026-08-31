import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

// Surface browser exceptions as failures, including asynchronous Tauri event cleanup.
const browserErrors = new WeakMap<Page, string[]>();
test.beforeEach(({ page }) => {
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on("pageerror", (error) => errors.push(error.message));
});
test.afterEach(({ page }) => {
  expect(browserErrors.get(page)).toEqual([]);
});

type PreflightWindow = Window & {
  __preflightCalls: string[];
  __preflightDigests: unknown[];
};

async function preparePreflightFailure(page: Page) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot }) => {
    const calls: string[] = [];
    const digests: unknown[] = [];
    let reviews = 0;
    let applied = false;
    const eventListeners = new Set<number>();
    let callbackId = 0;
    Object.assign(window, {
      isTauri: true,
      __preflightCalls: calls,
      __preflightDigests: digests,
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: (_event: string, id: number) => eventListeners.delete(id) },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++callbackId,
        unregisterCallback: () => undefined,
        metadata: { currentWindow: { label: "main" }, currentWebview: { label: "main" } },
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          calls.push(command);
          if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
          if (command === "desktop_plan_integrations") {
            reviews += 1;
            return {
              schema: "simplicio.desktop-integration-plan/v1", source: "runtime",
              planDigest: "sha256:" + (reviews === 1 ? "a" : "b").repeat(64),
              changes: [{ label: "codex", exists: applied, changed: !applied }],
            };
          }
          if (command === "desktop_repair_providers") {
            digests.push(args.planDigest);
            // Native preflight failed before starting the installer, for example on a query timeout.
            if (digests.length === 1) throw "integration_preflight_unavailable";
            if (args.planDigest !== "sha256:" + "b".repeat(64)) throw "integration_plan_changed_review_again";
            applied = true;
            return snapshot;
          }
          if (command === "plugin:event|listen") { const id = ++callbackId; eventListeners.add(id); return id; }
          if (command === "plugin:event|unlisten") return;
          throw "unexpected_preflight_recovery_command";
        },
      },
    });
  }, { snapshot });
}

async function calls(page: Page, command: string) {
  return page.evaluate((command) => (window as PreflightWindow).__preflightCalls.filter((item) => item === command).length, command);
}

async function digests(page: Page) {
  return page.evaluate(() => (window as PreflightWindow).__preflightDigests);
}

for (const view of ["setup", "providers"] as const) {
  test(`${view} requires a new plan and consent after preflight failure, without automatic installation (mocked IPC)`, async ({ page }) => {
    await preparePreflightFailure(page);
    await page.goto(`/?view=${view}`);
    const setup = view === "setup";
    const surface = setup ? page.getByRole("main") : page.getByRole("region", { name: "Configuração do MCP", exact: true });
    const review = page.getByRole("button", { name: setup ? "Configurar Simplicio" : "Revisar configuração MCP", exact: true });
    const apply = page.getByRole("button", { name: setup ? "Instalar e conectar" : "Aplicar configuração MCP", exact: true });
    const consent = surface.getByRole("checkbox", { name: /Autorizo o Runtime/ });

    await review.click();
    await expect(consent).not.toBeChecked();
    await expect(apply).toBeDisabled();
    await consent.check();
    await apply.click();
    await expect(page.getByRole("alert")).toContainText("O instalador não foi iniciado");
    await expect(page.getByRole("alert")).not.toContainText("alterações parciais");
    if (setup) await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
    await expect(consent).toHaveCount(0);
    await expect(apply).toHaveCount(0);
    expect(await digests(page)).toEqual(["sha256:" + "a".repeat(64)]);
    expect(await calls(page, "desktop_plan_integrations")).toBe(1);

    if (!setup) {
      const before = await calls(page, "refresh_desktop_snapshot");
      await page.getByRole("button", { name: "Verificar", exact: true }).click();
      await expect.poll(() => calls(page, "refresh_desktop_snapshot")).toBeGreaterThan(before);
      await expect(page.getByRole("button", { name: "Verificar", exact: true })).toBeEnabled();
      expect(await digests(page)).toHaveLength(1);
    }
    const reviewAgain = page.getByRole("button", { name: setup ? "Revisar novamente" : "Revisar configuração MCP", exact: true });
    await expect(reviewAgain).toBeEnabled();
    await reviewAgain.click();
    await expect(consent).not.toBeChecked();
    await expect(apply).toBeDisabled();
    expect(await calls(page, "desktop_plan_integrations")).toBe(2);
    expect(await digests(page)).toEqual(["sha256:" + "a".repeat(64)]);

    // A separate explicit confirmation submits only the newly reviewed digest.
    await consent.check();
    await apply.click();
    if (setup) {
      await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toBeVisible();
    } else {
      await expect(surface.getByRole("status")).toContainText("Configuração concluída pelo Runtime");
    }
    expect(await digests(page)).toEqual(["sha256:" + "a".repeat(64), "sha256:" + "b".repeat(64)]);
  });
}
