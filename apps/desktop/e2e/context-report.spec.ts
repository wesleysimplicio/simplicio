import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import type { ContextReport } from "../src/context_report";

async function contextBridge(page: Page, fail = false, reportPatch: Partial<ContextReport> = {}) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  const report: ContextReport = {
    schema: "simplicio.desktop-context-report/v1", source: "runtime", scope: "project_history",
    eventCount: 12, ledgerEventCount: 12, llmSpendEventCount: 0, baselineTokens: 1000, actualTokens: 650, savedTokens: 350, netTokens: 350,
    baselineKind: "mixed", confidence: "low", heuristicEventCount: 10, unlabeledEstimateCount: 1,
    proof: { measured: 9, estimated: 3, replayed: 0, benchmark: 0, unavailable: 0 },
    reportHash: `sha256:${"c".repeat(64)}`,
    ...reportPatch,
  };
  await page.addInitScript(({ snapshot, report, fail }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __contextCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_snapshot") return snapshot;
        if (command === "desktop_token_report") throw "token_ledger_unavailable";
        if (command === "desktop_context_report") {
          await new Promise((resolve) => setTimeout(resolve, 80));
          if (fail) throw "context_ledger_invalid";
          return report;
        }
        throw `Unexpected test command: ${command}`;
      },
    } });
  }, { snapshot, report, fail });
}

function contextMetric(page: Page, label: string) {
  return page.getByTestId("context-metrics").locator(":scope > div")
    .filter({ has: page.getByText(label, { exact: true }) }).locator("strong");
}

async function callsFor(page: Page, command: string) {
  return page.evaluate((command) => (window as Window & {
    __contextCalls: Array<{ command: string; args: Record<string, unknown> }>;
  }).__contextCalls.filter((call) => call.command === command), command);
}

test("project context savings remain usable when the separate usage ledger is absent", async ({ page }) => {
  await contextBridge(page);
  await page.goto("/?view=tokens");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/context project");
  await page.getByRole("button", { name: "Consultar economia de contexto", exact: true }).click();
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await expect(context).toContainText("350");
  await expect(context).toContainText("1.000");
  await expect(context).toContainText("650");
  await expect(context).toContainText("12 eventos");
  await expect(context).toContainText("Evidência mista");
  await expect(context).toContainText("não é consumo faturado");
  const calls = await page.evaluate(() => (window as unknown as { __contextCalls: Array<{ command: string; args: Record<string, unknown> }> }).__contextCalls.filter((item) => item.command === "desktop_context_report"));
  expect(calls).toEqual([{ command: "desktop_context_report", args: { repoPath: "/tmp/context project" } }]);
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/another project");
  await expect(context.getByTestId("context-metrics")).toHaveCount(0);
  await expect(context).toContainText("Consulte o histórico desta pasta");
});

test("an invalid savings ledger is not turned into successful savings or cost", async ({ page }) => {
  await contextBridge(page, true);
  await page.goto("/?view=tokens");
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await page.getByRole("button", { name: "Consultar economia de contexto", exact: true }).click();
  await expect(context.getByRole("alert")).toContainText("integridade");
  await expect(context.getByTestId("context-metrics")).toHaveCount(0);
  await expect(context).not.toContainText("R$");
  await expect(page.getByRole("button", { name: "Consultar economia de contexto", exact: true })).toBeEnabled();
});

test("negative net context usage is not replaced by positive gross reductions (mocked IPC)", async ({ page }) => {
  await contextBridge(page, false, { actualTokens: 1100, netTokens: -100 });
  await page.goto("/?view=tokens");
  await page.getByRole("button", { name: "Consultar economia de contexto", exact: true }).click();
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await expect(contextMetric(page, "Reduções registradas")).toHaveText("350");
  await expect(contextMetric(page, "Referência registrada")).toHaveText("1.000");
  await expect(contextMetric(page, "Com Simplicio")).toHaveText("1.100");
  await expect(contextMetric(page, "Diferença líquida")).toHaveText("-100");
  await expect(context).toContainText("Acumulado bruto do Runtime");
  await expect(context).toContainText("Mais tokens do que a referência");
  await expect(context).toContainText("Não o trate como economia líquida.");
  await expect(context).toContainText("não é consumo faturado");
});

test("mixed LLM spending leaves all context comparisons unavailable without hiding gross reductions (mocked IPC)", async ({ page }) => {
  await contextBridge(page, false, {
    eventCount: 10, llmSpendEventCount: 2,
    baselineTokens: null, actualTokens: null, netTokens: null,
  });
  await page.goto("/?view=tokens");
  await page.getByRole("button", { name: "Consultar economia de contexto", exact: true }).click();
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await expect(contextMetric(page, "Reduções registradas")).toHaveText("350");
  for (const label of ["Referência registrada", "Com Simplicio", "Diferença líquida"]) {
    await expect(contextMetric(page, label)).toHaveText("—");
  }
  await expect(context).toContainText("10 eventos de contexto · 12 eventos no histórico.");
  await expect(context).toContainText("O histórico também tem 2 eventos de uso de LLM.");
  await expect(context).toContainText("a comparação permanece indisponível");
  await expect(context).toContainText("Classificação informada pelo Runtime para o histórico completo.");
  await expect(context).not.toContainText("R$");
});

test("period and session filters do not replace or requery all-project context history (mocked IPC)", async ({ page }) => {
  await contextBridge(page);
  await page.goto("/?view=tokens");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/context-history-fixture");
  await page.getByRole("button", { name: "Consultar economia de contexto", exact: true }).click();
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  const metrics = context.getByTestId("context-metrics").locator("strong");
  const expectedMetrics = ["350", "1.000", "650", "350"];
  await expect(metrics).toHaveText(expectedMetrics);
  await context.getByText("Identificador do relatório", { exact: true }).click();
  const digest = context.locator(".context-digest code");
  await expect(digest).toHaveText(`sha256:${"c".repeat(64)}`);

  await page.getByRole("combobox", { name: "Período", exact: true }).selectOption("7d");
  await expect(metrics).toHaveText(expectedMetrics);
  await page.getByLabel("Sessão (opcional)").fill("session-fixture");
  await expect(metrics).toHaveText(expectedMetrics);
  await page.getByRole("combobox", { name: "Período", exact: true }).selectOption("custom");
  await page.getByRole("textbox", { name: "Início", exact: true }).fill("2026-08-01T00:00");
  await page.getByRole("textbox", { name: "Fim (exclusivo)", exact: true }).fill("2026-08-02T00:00");
  await expect(metrics).toHaveText(expectedMetrics);
  const usageCalls = (await callsFor(page, "desktop_token_report")).length;
  await page.getByRole("button", { name: "Consultar uso", exact: true }).click();
  await expect.poll(async () => (await callsFor(page, "desktop_token_report")).length).toBe(usageCalls + 1);
  await expect(page.getByRole("button", { name: "Consultar uso", exact: true })).toBeEnabled();
  expect((await callsFor(page, "desktop_token_report")).at(-1)).toMatchObject({
    args: { request: {
      repoPath: "/tmp/context-history-fixture", sessionId: "session-fixture",
      fromEpoch: expect.any(Number), toEpoch: expect.any(Number),
    } },
  });
  await expect(metrics).toHaveText(expectedMetrics);
  await expect(digest).toHaveText(`sha256:${"c".repeat(64)}`);
  await expect(context).toContainText("Todo o histórico da pasta acima.");
  await expect(context).toContainText("Os filtros de período e sessão se aplicam apenas ao uso registrado.");
  expect(await callsFor(page, "desktop_context_report")).toEqual([
    { command: "desktop_context_report", args: { repoPath: "/tmp/context-history-fixture" } },
  ]);
});
