import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { emptyWorkbench, WORKBENCH_KEY } from "../src/workbench";

type SettingsTestWindow = Window & {
  __settingsCalls: Array<{ command: string; args: Record<string, unknown> }>;
};
const project = { id: "project-" + "a".repeat(64), name: "Projeto A", path: "/tmp/Project A" };

test.use({ timezoneId: "UTC" });

async function nativeSettings(page: Page) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  snapshot.generatedAt = "unix:1704110400";
  const workbench = { ...emptyWorkbench(), projects: [project], selectedProjectId: project.id };
  await page.addInitScript(({ snapshot, workbench, storageKey }) => {
    window.localStorage.setItem(storageKey, JSON.stringify(workbench));
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, {
      isTauri: true,
      __settingsCalls: calls,
      __TAURI_INTERNALS__: {
        transformCallback: () => 1,
        unregisterCallback: () => undefined,
        metadata: { currentWindow: { label: "main" }, currentWebview: { label: "main" } },
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          calls.push({ command, args });
          if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
          // No auto-selected discovery candidate may hide a lost report scope.
          if (command === "desktop_usage_projects") return {
            schema: "simplicio.desktop-project-usage/v1", projects: [], candidateCount: 0,
            partial: false, reasons: [], directoriesVisited: 0, roots: [],
            scope: { kind: "conventional_roots_and_configured_repo" },
          };
          if (command === "desktop_token_report") throw "token_ledger_unavailable";
          if (command === "desktop_context_report") throw "context_ledger_unavailable";
          if (command === "desktop_consolidated_token_report") throw "consolidated_report_unavailable";
          if (command === "plugin:event|listen") return 1;
          if (command === "plugin:event|unlisten") return;
          throw "unexpected_settings_test_command";
        },
      },
    });
  }, { snapshot, workbench, storageKey: WORKBENCH_KEY });
}

async function tokenCalls(page: Page) {
  return page.evaluate(() => (window as SettingsTestWindow).__settingsCalls.filter((call) => call.command === "desktop_token_report"));
}

test("returning from settings preserves Project A and its token report repository (mocked IPC)", async ({ page }) => {
  await nativeSettings(page);
  await page.goto("/?view=project");
  await expect(page.getByRole("heading", { name: project.name, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Conta Simplicio", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
  await expect(page.getByRole("heading", { name: project.name, exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Consultar tokens/ }).click();
  const report = page.getByRole("region", { name: "Relatório individual", exact: true });
  const repository = report.getByLabel("Pasta do projeto (opcional)");
  await expect(repository).toHaveValue(project.path);
  await expect.poll(async () => (await tokenCalls(page)).length).toBeGreaterThan(0);
  await report.getByRole("button", { name: "Consultar uso", exact: true }).click();
  await expect(report.getByRole("button", { name: "Consultar uso", exact: true })).toBeEnabled();
  expect((await tokenCalls(page)).at(-1)?.args).toMatchObject({ request: { repoPath: project.path } });

  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByRole("button", { name: "Runtime e diagnóstico", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Runtime e diagnóstico", exact: true })).toBeVisible();
  const beforeReturn = (await tokenCalls(page)).length;
  await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Relatório de tokens", exact: true })).toBeVisible();
  await expect(repository).toHaveValue(project.path);
  await expect.poll(async () => (await tokenCalls(page)).length).toBeGreaterThan(beforeReturn);
  expect((await tokenCalls(page)).at(-1)?.args).toMatchObject({ request: { repoPath: project.path } });
});

test("diagnostics renders the native Unix snapshot date without Invalid Date (mocked IPC)", async ({ page }) => {
  await nativeSettings(page);
  await page.goto("/?view=diagnostics");
  await expect(page.getByRole("heading", { name: "Runtime e diagnóstico", exact: true })).toBeVisible();
  const timestamp = page.locator(".preference-row").filter({ has: page.getByText("Leitura do snapshot", { exact: true }) });
  await expect(timestamp).toContainText("01/01/2024, 12:00:00");
  await expect(timestamp).not.toContainText("Invalid Date");
  await expect(timestamp).not.toContainText("unix:");
});
