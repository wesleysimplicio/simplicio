import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

async function mockNativeBridge(page: Page, options: { signedOut?: boolean; failSetup?: boolean; failExport?: boolean; pauseSetup?: boolean; failVerification?: boolean; loginState?: "inactive" | "unknown" } = {}) {
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
    let installed = false;
    let accessState = snapshot.access.state;
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __desktopTestCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_login") { await new Promise((resolve) => setTimeout(resolve, 50)); signedOut = false; accessState = options.loginState ?? "active"; return { ...snapshot, access: { ...snapshot.access, state: accessState } }; }
        if (command === "desktop_logout") signedOut = true;
        if (command === "refresh_desktop_snapshot" && installed && options.failVerification) throw "test_final_snapshot_failed";
        if (["desktop_snapshot", "refresh_desktop_snapshot", "desktop_logout"].includes(command)) return { ...snapshot, access: { ...snapshot.access, state: signedOut ? "signed_out" : accessState } };
        if (command === "desktop_plan_integrations") return { schema: "simplicio.desktop-integration-plan/v1", source: "runtime", planDigest: `sha256:${(installed ? "b" : "a").repeat(64)}`, changes: [{ label: "codex", changed: !installed, exists: true }] };
        if (command === "desktop_repair_providers") {
          if (options.pauseSetup) await new Promise((resolve) => Object.assign(window, { __desktopCompleteSetup: resolve }));
          if (options.failSetup) throw "integration_plan_changed_review_again";
          installed = true;
          return snapshot;
        }
        if (command === "desktop_validate_project") {
          if (args.path === "/missing") throw "project_path_invalid";
          return { id: `project-${"b".repeat(64)}`, name: "My project", path: "/tmp/project with spaces" };
        }
        if (command === "desktop_open_project") return;
        if (command === "desktop_export_snapshot") {
          await new Promise((resolve) => setTimeout(resolve, 150));
          if (options.failExport) throw "snapshot_export_permission_denied";
          return { schema: "simplicio.desktop-snapshot-export/v1", kind: args.kind, path: `/Downloads/simplicio-${args.kind}.json`, bytes: 1024 };
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
  await expect(page.getByRole("heading", { name: "Integrações MCP", exact: true })).toBeVisible();
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
  const individual = page.getByRole("region", { name: "Relatório individual", exact: true });
  await expect(individual.locator(".token-metric").first()).toContainText("137");
  await page.getByRole("combobox", { name: "Período", exact: true }).selectOption("7d");
  await page.getByLabel("Sessão (opcional)").fill("session-test");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/project with spaces");
  await page.getByRole("button", { name: "Consultar uso" }).click();
  await expect(individual.locator(".token-metric").first()).toContainText("137");
  await page.screenshot({ path: testInfo.outputPath("token-report.png"), fullPage: true });
  const requests = await calls(page, "desktop_token_report");
  expect(requests.at(-1)?.args.request).toMatchObject({ sessionId: "session-test", repoPath: "/tmp/project with spaces" });
  await page.getByRole("button", { name: "Exportar JSON" }).dblclick();
  await expect(individual.getByRole("status")).toContainText("Exportado para /Downloads/simplicio-token-usage.json");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  await expect(individual.getByRole("status")).toContainText("Exportado para /Downloads/simplicio-token-usage.csv");
  expect(await calls(page, "desktop_export_token_report")).toEqual(["json", "csv"].map((format) => ({
    command: "desktop_export_token_report", args: { reportHash: `sha256:${"a".repeat(64)}`, format },
  })));
  await page.getByLabel("Pasta do projeto (opcional)").fill("/missing");
  await page.getByRole("button", { name: "Consultar uso" }).click();
  await expect(individual.getByRole("alert")).toContainText("não significa consumo zero");
  await expect(individual.locator(".token-metric")).toHaveCount(0);
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

test("active login opens guided setup and duplicate account effects stay serialized", async ({ page }) => {
  await mockNativeBridge(page, { signedOut: true });
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Começar", exact: true }).click();
  await page.getByRole("button", { name: /Continuar com Google/ }).dblclick();
  await expect(page.getByRole("heading", { name: "Um bom começo." })).toBeVisible();
  expect(await calls(page, "desktop_plan_integrations")).toHaveLength(0);
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(0);
  await page.getByRole("button", { name: "Agora não" }).click();
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_login")).toHaveLength(1);
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByRole("button", { name: "Modelos e skills", exact: true })).toHaveCount(0);
});

test("hidden model inventory remains available as a direct preview (mocked IPC)", async ({ page }) => {
  await mockNativeBridge(page);
  await page.goto("/?view=models");
  await expect(page.getByText(/Nenhum modelo foi informado/)).toBeVisible();
});

test("guided setup follows reviewed Runtime operations without fake progress or automatic effects (mocked IPC)", async ({ page }, testInfo) => {
  await mockNativeBridge(page, { pauseSetup: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByRole("button", { name: "Instalação guiada", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Um bom começo." })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("setup-welcome.png"), fullPage: true });
  await page.getByRole("button", { name: "Configurar Simplicio" }).click();
  await expect(page.getByRole("heading", { name: "Tudo pronto para revisar." })).toBeVisible();
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(0);
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "2");
  const install = page.getByRole("button", { name: "Instalar e conectar" });
  await expect(install).toBeDisabled();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.screenshot({ path: testInfo.outputPath("setup-review.png"), fullPage: true });
  await install.dblclick();
  await expect(page.getByRole("heading", { name: "Configurando o Simplicio…" })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "2");
  await expect(page.getByRole("button", { name: "Voltar ao app" })).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Instalar e registrar o MCP");
  await expect(page.getByText(/Esta operação não oferece cancelamento seguro depois de iniciada/)).toBeVisible();
  await page.getByRole("button", { name: "Mostrar detalhes" }).click();
  await expect(page.getByRole("region", { name: "Detalhes da configuração" })).toContainText(`sha256:${"a".repeat(64)}`);
  await page.screenshot({ path: testInfo.outputPath("setup-progress.png"), fullPage: true });
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(1);
  await page.evaluate(() => (window as unknown as { __desktopCompleteSetup: () => void }).__desktopCompleteSetup());
  await expect(page.getByRole("heading", { name: "Configuração concluída." })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "4");
  await expect(page.getByText(/Registro não significa conexão ativa/)).toBeVisible();
  expect(await calls(page, "refresh_desktop_snapshot")).toHaveLength(2);
  expect(await calls(page, "desktop_plan_integrations")).toHaveLength(2);
  await page.getByRole("button", { name: "Abrir Simplicio" }).click();
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
});

test("guided setup can be abandoned before consent and failure only offers a new review (mocked IPC)", async ({ page }, testInfo) => {
  await mockNativeBridge(page, { failSetup: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio" }).click();
  await page.getByRole("button", { name: "Voltar ao app" }).click();
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(0);
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByRole("button", { name: "Instalação guiada", exact: true }).click();
  await page.getByRole("button", { name: "Configurar Simplicio" }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar" }).click();
  await expect(page.getByRole("heading", { name: "Não foi possível concluir." })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("O plano mudou");
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "2");
  await expect(page.getByRole("heading", { name: "Configuração concluída." })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("setup-failure.png"), fullPage: true });
  await page.getByRole("button", { name: "Revisar novamente" }).click();
  await expect(page.getByRole("button", { name: "Instalar e conectar" })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(1);
});

test("a failed final verification cannot turn an applied plan into a success screen (mocked IPC)", async ({ page }) => {
  await mockNativeBridge(page, { failVerification: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio" }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar" }).click();
  await expect(page.getByRole("alert")).toContainText("o plano foi aplicado, mas a verificação final falhou", { ignoreCase: true });
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "3");
  await expect(page.getByRole("button", { name: "Revisar novamente" })).toHaveCount(0);
  await page.getByRole("button", { name: "Atualizar diagnóstico" }).click();
  await expect(page.getByRole("heading", { name: "Runtime e diagnóstico", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_repair_providers")).toHaveLength(1);
});

test("login never bypasses inactive or unknown entitlement into guided installation (mocked IPC)", async ({ browser, baseURL }) => {
  for (const state of ["inactive", "unknown"] as const) {
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    await mockNativeBridge(page, { signedOut: true, loginState: state });
    await page.goto("/");
    await page.getByRole("button", { name: "Começar", exact: true }).click();
    await page.getByRole("button", { name: /Continuar com Google/ }).click();
    await expect(page.getByRole("heading", { name: state === "inactive" ? "Ative o Simplicio" : "Tente novamente" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Configurar Simplicio" })).toHaveCount(0);
    expect(await calls(page, "desktop_repair_providers")).toHaveLength(0);
    await context.close();
  }
});

test("local projects use native validation, scoped token queries, open-folder IPC and non-destructive removal (mocked IPC)", async ({ page }) => {
  await mockNativeBridge(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await page.getByLabel("Caminho da pasta").fill("/missing");
  await page.getByRole("dialog").getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Não foi possível adicionar");
  await page.getByLabel("Caminho da pasta").fill("/tmp/project with spaces");
  await page.getByRole("dialog").getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Abrir pasta/ }).click();
  expect(await calls(page, "desktop_open_project")).toEqual([{ command: "desktop_open_project", args: { path: "/tmp/project with spaces" } }]);
  await page.reload();
  await expect(page.getByRole("heading", { name: "My project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Consultar tokens/ }).click();
  await expect(page.getByLabel("Pasta do projeto (opcional)")).toHaveValue("/tmp/project with spaces");
  expect((await calls(page, "desktop_token_report")).at(-1)?.args.request).toMatchObject({ repoPath: "/tmp/project with spaces" });
  await page.getByRole("button", { name: "Voltar", exact: true }).click();
  await page.getByRole("button", { name: "Remover da lista" }).click();
  await expect(page.getByText(/Nenhum arquivo da pasta será excluído/)).toBeVisible();
  await page.getByRole("button", { name: "Manter projeto" }).click();
  await page.getByRole("button", { name: "Remover da lista" }).click();
  await page.getByRole("button", { name: "Confirmar remoção da lista" }).click();
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_validate_project")).toHaveLength(0); // Reload reset mock calls, not persisted projects.
});

test("diagnostic and activity exports go through native commands with no frontend file bodies (mocked IPC)", async ({ page }) => {
  await mockNativeBridge(page);
  await page.goto("/?view=diagnostics");
  await page.getByRole("button", { name: "Exportar diagnóstico" }).dblclick();
  await expect(page.getByRole("status")).toContainText("/Downloads/simplicio-diagnostic.json");
  expect(await calls(page, "desktop_export_snapshot")).toEqual([{ command: "desktop_export_snapshot", args: { kind: "diagnostic", filters: {} } }]);
  await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
  await page.getByRole("button", { name: "Atividade", exact: true }).click();
  await page.getByRole("button", { name: "atenção", exact: true }).click();
  await page.getByRole("button", { name: "Exportar recibos" }).click();
  await expect(page.getByRole("status")).toContainText("/Downloads/simplicio-activity.json");
  expect((await calls(page, "desktop_export_snapshot")).at(-1)?.args).toEqual({ kind: "activity", filters: { status: "attention", provider: "all" } });
});
