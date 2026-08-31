import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

async function installBridge(page: Page, delay = 60, partial = false, unavailableRoots: string[] = []) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot, delay, partial, unavailableRoots }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __projectCalls: calls, __TAURI_INTERNALS__: { invoke: async (command: string, args: Record<string, unknown> = {}) => {
      calls.push({ command, args });
      if (command === "desktop_snapshot") return snapshot;
      if (command === "desktop_usage_projects") {
        await new Promise((resolve) => setTimeout(resolve, delay));
        return { schema: "simplicio.desktop-project-usage/v1", candidateCount: 2, partial, reasons: partial ? [unavailableRoots.length ? "root_timeout" : "deadline"] : [], unavailableRoots, directoriesVisited: 6,
          scope: { kind: "conventional_roots_and_configured_repo", maxDepth: 5, maxDirectories: 4000, maxResults: 64, deadlineMs: 2000 },
          roots: [{ name: "Projetos", path: "/tmp/Projetos" }], projects: [
            { id: `project-${"a".repeat(64)}`, name: "Material didático", path: "/tmp/Projetos/aulas", evidenceType: "context", lastModifiedEpoch: 1788180001 },
            { id: `project-${"b".repeat(64)}`, name: "Runtime", path: "/tmp/Projetos/runtime", evidenceType: "both", lastModifiedEpoch: 1788180000 },
          ] };
      }
      if (command === "desktop_token_report") throw "token_ledger_unavailable";
      if (command === "desktop_context_report") {
        await new Promise((resolve) => setTimeout(resolve, 90));
        const savedTokens = args.repoPath === "/tmp/Projetos/aulas" ? 350 : 125;
        return { schema: "simplicio.desktop-context-report/v1", source: "runtime", scope: "project_history",
          eventCount: 12, ledgerEventCount: 12, llmSpendEventCount: 0, baselineTokens: 1000, actualTokens: 1000 - savedTokens, savedTokens, netTokens: savedTokens,
          baselineKind: "mixed", confidence: "low", heuristicEventCount: 10, unlabeledEstimateCount: 1,
          proof: { measured: 9, estimated: 3, replayed: 0, benchmark: 0, unavailable: 0 }, reportHash: `sha256:${"d".repeat(64)}` };
      }
      throw `Unexpected test command: ${command}`;
    } } });
  }, { snapshot, delay, partial, unavailableRoots });
}

test("discovers real-ledger candidates, selects the newest and loads only the selected project", async ({ page }) => {
  await installBridge(page);
  await page.goto("/?view=tokens");
  await expect(page.getByLabel("Pasta do projeto (opcional)")).toHaveValue("/tmp/Projetos/aulas");
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await expect(context.getByTestId("context-metrics")).toContainText("350");
  const projects = page.getByRole("region", { name: "Pastas com uso do Simplicio" });
  await expect(projects).toContainText("2 pastas encontradas");
  await expect(projects).toContainText("Um ledger encontrado é um candidato");
  await page.getByLabel("Projetos com uso do Simplicio").selectOption(`project-${"b".repeat(64)}`);
  await expect(page.getByLabel("Pasta do projeto (opcional)")).toHaveValue("/tmp/Projetos/runtime");
  await expect(context.getByTestId("context-metrics")).toContainText("125");
  await expect(context.getByTestId("context-metrics")).not.toContainText("350");
  const calls = await page.evaluate(() => (window as unknown as { __projectCalls: Array<{ command: string; args: Record<string, unknown> }> }).__projectCalls);
  expect(calls.filter((call) => call.command === "desktop_context_report").map((call) => call.args.repoPath)).toEqual(["/tmp/Projetos/aulas", "/tmp/Projetos/runtime"]);
  expect(calls.filter((call) => call.command === "desktop_usage_projects")).toHaveLength(1);
});

test("late discovery does not overwrite a manually entered folder and reports partial scope", async ({ page }) => {
  await installBridge(page, 800, true);
  await page.goto("/?view=tokens");
  await page.getByLabel("Pasta do projeto (opcional)").fill("/tmp/minha-escolha");
  await expect(page.getByRole("region", { name: "Pastas com uso do Simplicio" })).toContainText("Descoberta parcial");
  await expect(page.getByLabel("Pasta do projeto (opcional)")).toHaveValue("/tmp/minha-escolha");
  await expect(page.getByTestId("context-metrics")).toHaveCount(0);
  const contextCalls = await page.evaluate(() => (window as unknown as { __projectCalls: Array<{ command: string }> }).__projectCalls.filter((call) => call.command === "desktop_context_report"));
  expect(contextCalls).toHaveLength(0);
});

test("keeps completed projects usable when another root times out", async ({ page }) => {
  await installBridge(page, 60, true, ["Desktop"]);
  await page.goto("/?view=tokens");
  const projects = page.getByRole("region", { name: "Pastas com uso do Simplicio" });
  const context = page.getByRole("region", { name: "Economia de contexto", exact: true });
  await expect(projects).toContainText("2 pastas encontradas");
  await expect(projects).toContainText("Descoberta parcial");
  await expect(projects).toContainText("Locais não concluídos: Desktop");
  await expect(context.getByTestId("context-metrics")).toContainText("350");
  await page.getByLabel("Projetos com uso do Simplicio").selectOption(`project-${"b".repeat(64)}`);
  await expect(page.getByLabel("Pasta do projeto (opcional)")).toHaveValue("/tmp/Projetos/runtime");
  await expect(context.getByTestId("context-metrics")).toContainText("125");
  await expect(projects.getByRole("button", { name: "Escolher outra pasta…" })).toBeEnabled();
  const calls = await page.evaluate(() => (window as unknown as { __projectCalls: Array<{ command: string; args: Record<string, unknown> }> }).__projectCalls);
  expect(calls.filter((call) => call.command === "desktop_context_report").map((call) => call.args.repoPath)).toEqual(["/tmp/Projetos/aulas", "/tmp/Projetos/runtime"]);
  expect(calls.filter((call) => call.command === "desktop_usage_projects")).toHaveLength(1);
});
