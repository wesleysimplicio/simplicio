import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

const NO_DATA = {
  schema: "simplicio.desktop-unified-usage/v1",
  generated_at_epoch: 0,
  query: { provider: "openai" },
  rows: [],
  totals: {
    input_tokens: 0,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    reported_output_tokens: 0,
    output_tokens: 0,
    reasoning_tokens: 0,
    total_tokens: 0,
    cost_usd: 0,
    event_count: 0,
  },
  metadata: {
    generated_by: "runtime_usage_ledger",
    source: "runtime",
    generated_at_epoch: 0,
    report_digest: "sha256:a78554c978a2fb65c8aec801d42b93539025b27ec9715aa54d9f8be45a2142f8",
    revision: "sha256:5eed768be80b989f7a0d53033265b00f398bd7e88ba111f2c301936764118f37",
    pricing_version: null,
    pricing_sources: [],
    coverage: {
      status: "no_data",
      missing_usage_events: 0,
      unpriced_events: 0,
      providers: [],
      reason: "no_matching_usage",
    },
    redacted: true,
  },
};

test("snapshot no-data is honest and export retains the queried time range", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.clock.install({ time: new Date("2026-09-05T22:00:00Z") });
  await page.addInitScript(({ snapshot, projection }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __usageCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
        if (command === "desktop_preparation_status") return true;
        if (command === "desktop_snapshot") return snapshot;
        if (command === "desktop_unified_usage") return projection;
        if (command === "desktop_export_unified_usage") return {
          schema: "simplicio.desktop-unified-usage-export/v1", format: args.format,
          path: "/Users/test/Downloads/usage.json", bytes: 128, report_digest: projection.metadata.report_digest,
        };
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "fixture_unavailable";
      },
    } });
  }, { snapshot, projection: NO_DATA });
  await page.goto("/");
  const home = page.getByRole("region", { name: "Uso observado do Runtime" });
  await expect(home).toContainText("sem dados");
  await expect(home).not.toContainText("US$ 0");
  await page.getByRole("button", { name: "Relatório de tokens", exact: true }).click();
  await page.getByRole("button", { name: "Consultar uso unificado", exact: true }).click();
  await expect(page.getByRole("button", { name: "Exportar uso JSON" })).toBeEnabled();
  const queried = await page.evaluate(() => (window as unknown as { __usageCalls: Array<{ command: string; args: Record<string, unknown> }> }).__usageCalls.filter(c => c.command === "desktop_unified_usage").at(-1)?.args);
  await page.clock.fastForward(65_000);
  await page.getByRole("button", { name: "Exportar uso JSON" }).click();
  await expect(page.getByRole("region", { name: "Uso unificado", exact: true })).toContainText("Projeção exportada");
  const exported = await page.evaluate(() => (window as unknown as { __usageCalls: Array<{ command: string; args: Record<string, unknown> }> }).__usageCalls.find(c => c.command === "desktop_export_unified_usage")?.args);
  expect(exported?.query).toEqual(queried?.query);
  expect(exported?.repoPath).toEqual(queried?.repoPath);
  const commands = await page.evaluate(() => (window as unknown as { __usageCalls: Array<{ command: string }> }).__usageCalls.map(c => c.command));
  expect(commands).not.toContain("desktop_usage_changefeed");
});
