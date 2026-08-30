import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

async function mockNativeBridge(page: Page, options: { signedOut?: boolean; failSetup?: boolean; failExport?: boolean } = {}) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  const report = {
    schema: "workspace.token-analytics-report/v1", generated_by: "sqlite_ledger", now_epoch: 1788123153,
    session_id: null, timezone_offset_seconds: 0, report_hash: `sha256:${"a".repeat(64)}`,
    periods: ["today", "7d", "1m", "3m", "6m", "12m"].map((window) => ({ window, from_epoch: 1788000000, to_epoch: 1788123154,
      totals: { sample_count: 2, input_tokens: 100, cached_input_tokens: 20, output_tokens: 30, reasoning_tokens: 7, paid_remote_tokens: 137, total_tokens: 137, missing_usage_events: 1, receipt_count: 2 },
    })),
  };
  await page.addInitScript(({ snapshot, report, options }) => {
    let signedOut = Boolean(options.signedOut);
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __desktopTestCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_login") { await new Promise((resolve) => setTimeout(resolve, 50)); signedOut = false; return snapshot; }
        if (command === "desktop_logout") signedOut = true;
        if (["desktop_snapshot", "refresh_desktop_snapshot", "desktop_logout"].includes(command)) return signedOut ? { ...snapshot, access: { ...snapshot.access, state: "signed_out" } } : snapshot;
        if (command === "desktop_plan_integrations") return { schema: "simplicio.desktop-integration-plan/v1", source: "runtime", planDigest: `sha256:${"a".repeat(64)}`, changes: [{ label: "codex", changed: true, exists: true }] };
        if (command === "desktop_repair_providers") {
          if (options.failSetup) throw "integration_plan_changed_review_again";
          return snapshot;
        }
        if (command === "desktop_token_report") {
          const query = args.request as { repoPath?: string; sessionId?: string; fromEpoch?: number; toEpoch?: number; timezoneOffsetSeconds: number };
          if (query.repoPath === "/missing") throw "token_ledger_unavailable";
          return { ...report, timezone_offset_seconds: query.timezoneOffsetSeconds, session_id: query.sessionId ?? null,
            periods: query.fromEpoch === undefined ? report.periods : [...report.periods, { ...report.periods[0], window: "custom", from_epoch: query.fromEpoch, to_epoch: query.toEpoch }],
          };
        }
        if (command === "desktop_export_token_report") {
          await new Promise((resolve) => setTimeout(resolve, 150));
          if (options.failExport) throw "token_export_permission_denied";
          return { schema: "simplicio.desktop-token-export/v1", format: args.format, path: `/Downloads/simplicio-token-usage.${args.format}`, bytes: 1024 };
        }
        throw `Unexpected test IPC command: ${command}`;
      },
    } });
  }, { snapshot, report, options });
}

async function calls(page: Page, command: string) {
  return page.evaluate((command) => (window as unknown as { __desktopTestCalls: Array<{ command: string; args: Record<string, unknown> }> }).__desktopTestCalls.filter((row) => row.command === command), command);
}

test("normal navigation reaches MCP setup and never installs without review and consent", async ({ page }) => {
  await mockNativeBridge(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Integrações MCP", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(0);
  await page.getByRole("button", { name: "Revisar configuração MCP" }).click();
  const apply = page.getByRole("button", { name: "Aplicar configuração MCP" });
  await expect(apply).toBeDisabled();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await apply.click();
  await expect(page.getByText(/Configuração concluída pelo Runtime/)).toBeVisible();
  expect(await calls(page, "desktop_repair_providers")).toEqual([{ command: "desktop_repair_providers", args: { planDigest: `sha256:${"a".repeat(64)}` } }]);
});

test("changed setup plans surface an actionable error without false success", async ({ page }) => {
  await mockNativeBridge(page, { failSetup: true });
  await page.goto("/?view=providers");
  await page.getByRole("button", { name: "Revisar configuração MCP" }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Aplicar configuração MCP" }).click();
  await expect(page.getByRole("alert")).toContainText("O plano mudou");
  await expect(page.getByRole("button", { name: "Aplicar configuração MCP" })).toBeHidden();
  await expect(page.getByText(/Configuração concluída pelo Runtime/)).toHaveCount(0);
});

test("token reports use filtered queries and send only a native report digest for export (mocked IPC)", async ({ page }, testInfo) => {
  await mockNativeBridge(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Relatório de tokens", exact: true }).click();
  await expect(page.locator(".token-metric").first()).toContainText("137");
  await page.getByRole("combobox", { name: "Período", exact: true }).selectOption("7d");
  await page.getByLabel("Sessão (opcional)").fill("session-test");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/project with spaces");
  await page.getByRole("button", { name: "Consultar uso" }).click();
  await expect(page.locator(".token-metric").first()).toContainText("137");
  await page.screenshot({ path: testInfo.outputPath("token-report.png"), fullPage: true });
  const requests = await calls(page, "desktop_token_report");
  expect(requests.at(-1)?.args.request).toMatchObject({ sessionId: "session-test", repoPath: "/tmp/project with spaces" });
  await page.getByRole("button", { name: "Exportar JSON" }).dblclick();
  await expect(page.getByRole("status")).toContainText("Exportado para /Downloads/simplicio-token-usage.json");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  await expect(page.getByRole("status")).toContainText("Exportado para /Downloads/simplicio-token-usage.csv");
  expect(await calls(page, "desktop_export_token_report")).toEqual(["json", "csv"].map((format) => ({
    command: "desktop_export_token_report", args: { reportHash: `sha256:${"a".repeat(64)}`, format },
  })));
  await page.getByLabel("Pasta do projeto (opcional)").fill("/missing");
  await page.getByRole("button", { name: "Consultar uso" }).click();
  await expect(page.getByRole("alert")).toContainText("não significa consumo zero");
  await expect(page.locator(".token-metric")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Exportar JSON" })).toHaveCount(0);
  await expect(page.getByText(/Exportado para/)).toHaveCount(0);
});

test("native export failures remain visible and never claim a download succeeded (mocked IPC)", async ({ page }) => {
  await mockNativeBridge(page, { failExport: true });
  await page.goto("/?view=tokens");
  const button = page.getByRole("button", { name: "Exportar JSON" });
  await button.click();
  await expect(page.getByRole("alert")).toContainText("O sistema não permitiu salvar em Downloads");
  await expect(page.getByText(/Exportado para/)).toHaveCount(0);
  await expect(button).toBeEnabled();
});

test("active login returns to Today and duplicate account effects stay serialized", async ({ page }) => {
  await mockNativeBridge(page, { signedOut: true });
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: /Continuar com Google/ }).dblclick();
  await expect(page.getByRole("heading", { name: "Today", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_login")).toHaveLength(1);
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByText(/Nenhum modelo foi informado/)).toBeVisible();
});
