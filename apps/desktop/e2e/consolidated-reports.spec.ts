import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

async function mockReports(page: Page, mode: "ready" | "missing" | "invalid" | "partial" | "stale" | "unreported" = "ready", delay = 0) {
  await page.addInitScript(({ snapshot, mode, delay }) => {
    const calls: Array<{ command: string; args: Record<string, any> }> = [];
    const projects = ["aulas", "runtime"].map((name, i) => ({ id: `project-${String(i).repeat(64)}`, name, path: `/tmp/${name}`, evidenceType: "usage", lastModifiedEpoch: 1788180000 }));
    Object.assign(window, { __reportCalls: calls, __TAURI_INTERNALS__: { invoke: async (command: string, args: Record<string, any> = {}) => {
      calls.push({ command, args });
      if (command === "desktop_snapshot") return snapshot;
      if (command === "desktop_usage_projects") return { schema: "simplicio.desktop-project-usage/v1", projects, candidateCount: 2, partial: mode === "partial", reasons: mode === "partial" ? ["deadline"] : [], directoriesVisited: 2,
        roots: [{ name: "Projetos", path: "/tmp" }], scope: { kind: "conventional_roots_and_configured_repo" } };
      if (command === "desktop_token_report") throw "token_ledger_unavailable";
      if (command === "desktop_context_report") throw "context_ledger_unavailable";
      if (command === "desktop_consolidated_token_report") {
        await new Promise(resolve => setTimeout(resolve, delay));
        const request = args.request;
        const hash = `sha256:${"a".repeat(64)}`;
        const totals = { sample_count: 2, input_tokens: 100, cached_input_tokens: 20, output_tokens: 40, reasoning_tokens: 10, paid_remote_tokens: 150, total_tokens: 150, missing_usage_events: 0, receipt_count: 2 };
        if (mode === "unreported") Object.assign(totals, { input_tokens: 0, cached_input_tokens: 0, output_tokens: 0, reasoning_tokens: 0, paid_remote_tokens: 0, total_tokens: 0, missing_usage_events: 2 });
        const entries = request.repoPaths.map((path: string, i: number) => ({ id: `p-${i}`, path, name: path.split("/").pop(), status: mode === "missing" ? "missing" : mode === "partial" && i === 1 ? "timeout" : "ready", totals: mode === "missing" || mode === "partial" && i === 1 ? null : totals, reportHash: mode === "missing" || mode === "partial" && i === 1 ? null : hash }));
        const count = entries.filter((p: any) => p.status === "ready").length;
        return { schema: "simplicio.desktop-consolidated-tokens/v1", source: "runtime", ...request, generatedAtEpoch: request.toEpoch,
          projects: entries, totals: count ? Object.fromEntries(Object.entries(totals).map(([key, value]) => [key, value * count])) : null,
          reportHash: mode === "invalid" || mode === "stale" && calls.filter(c => c.command === command).length > 1 ? "unverified" : hash };
      }
      throw `Unexpected test command: ${command}`;
    } } });
  }, { snapshot: { ...createDemoSnapshot("active"), source: "runtime" }, mode, delay });
}

test("consolidates all discovered projects and all five requested intervals with accessible charts", async ({ page }) => {
  await mockReports(page);
  await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByLabel("Totais consolidados")).toContainText("300");
  await expect(report.getByRole("img", { name: "Composição dos tokens registrados" })).toBeVisible();
  for (const label of ["7 dias", "30 dias", "3 meses", "6 meses", "12 meses"]) {
    await report.getByRole("button", { name: label, exact: true }).click();
    await expect(report.getByLabel("Totais consolidados")).toContainText("300");
    await expect(report.getByRole("button", { name: label, exact: true })).toHaveAttribute("aria-pressed", "true");
  }
  const calls = await page.evaluate(() => (window as any).__reportCalls.filter((c: any) => c.command === "desktop_consolidated_token_report"));
  expect(calls).toHaveLength(6);
  for (const call of calls) expect(call.args.request.repoPaths).toEqual(["/tmp/aulas", "/tmp/runtime"]);
  expect(calls[1].args.request.toEpoch - calls[1].args.request.fromEpoch).toBe(7 * 86400);
  expect(calls[2].args.request.toEpoch - calls[2].args.request.fromEpoch).toBe(30 * 86400);
  await page.screenshot({ path: "/tmp/simplicio-consolidated-report.png", fullPage: true });
  await report.locator(".consolidated-charts").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/simplicio-consolidated-charts.png" });
});

test("preserves partial results and identifies timed out projects", async ({ page }) => {
  await mockReports(page, "partial"); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report).toContainText("Cobertura parcial");
  await expect(report.getByLabel("Totais consolidados")).toContainText("150");
  await expect(report.getByRole("table")).toContainText("Sem resposta");
});

test("missing ledgers do not produce charts or a false zero", async ({ page }) => {
  await mockReports(page, "missing"); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report).toContainText("Ausência de telemetria não significa consumo zero");
  await expect(report.getByRole("img")).toHaveCount(0);
  await expect(report.getByLabel("Totais consolidados")).toContainText("—");
});

test("keeps known event and receipt counts when all events lack token usage", async ({ page }) => {
  await mockReports(page, "unreported"); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  const metrics = report.getByLabel("Totais consolidados");
  await expect(metrics.getByRole("article").filter({ hasText: "Tokens registrados" })).toContainText("—");
  await expect(metrics.getByRole("article").filter({ hasText: "Eventos registrados" })).toContainText("4");
  await expect(metrics.getByRole("article").filter({ hasText: "Recibos" })).toContainText("4");
  await expect(report.getByRole("img")).toHaveCount(0);
  await expect(report).toContainText("Cobertura parcial");
});

test("rejects malformed reports without showing their totals", async ({ page }) => {
  await mockReports(page, "invalid"); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByRole("alert")).toContainText("Não foi possível validar");
  await expect(report.getByLabel("Totais consolidados")).toHaveCount(0);
});

test("blocks duplicate refresh and filter changes while a batch is pending", async ({ page }) => {
  await mockReports(page, "ready", 600); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByRole("button", { name: "7 dias", exact: true })).toBeDisabled();
  await expect(report.getByRole("button", { name: "Atualizar consolidado" })).toBeDisabled();
  await expect(report.getByLabel("Totais consolidados")).toBeVisible();
  const count = await page.evaluate(() => (window as any).__reportCalls.filter((c: any) => c.command === "desktop_consolidated_token_report").length);
  expect(count).toBe(1);
});

test("charts and project table remain usable at narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await mockReports(page); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByRole("table")).toBeVisible();
  expect(await report.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

test("adds a manually queried project to the consolidated scope without losing discovered projects", async ({ page }) => {
  await mockReports(page); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByLabel("Totais consolidados")).toContainText("300");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/third");
  await page.getByRole("button", { name: "Consultar uso", exact: true }).click();
  await expect(report.getByLabel("Totais consolidados")).toContainText("450");
  await expect(report.getByRole("table")).toContainText("/tmp/third");
});

test("never leaves old totals or charts under a changed period when the next response fails", async ({ page }) => {
  await mockReports(page, "stale", 200); await page.goto("/?view=tokens");
  const report = page.getByRole("region", { name: "Relatório consolidado", exact: true });
  await expect(report.getByLabel("Totais consolidados")).toContainText("300");
  await report.getByRole("button", { name: "7 dias", exact: true }).click();
  await expect(report.getByLabel("Totais consolidados")).toHaveCount(0);
  await expect(report.getByRole("alert")).toBeVisible();
  await expect(report.getByRole("img")).toHaveCount(0);
});
