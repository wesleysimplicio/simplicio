import { expect, test, type Page, type Route } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { DESKTOP_RELEASES_API, DESKTOP_RELEASES_URL, DESKTOP_UPDATE_EVENT } from "../src/desktop_updates";

type UpdatesWindow = Window & {
  __updatesCalls: Array<{ command: string; args: Record<string, unknown> }>;
  __updatesMenu: () => void;
  __updatesListeners: () => number;
  __updatesResolveOpen: (index: number) => void;
  __updatesRejectOpen: (index: number) => void;
  __updatesResolveVersion: () => void;
  __updatesState: Record<string, unknown>;
  __updatesRejectDownload: () => void;
  __updatesCompleteDownload: () => void;
};

async function mockUpdates(page: Page, options: { holdVersion?: boolean; version?: string; notes?: string } = {}) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.clock.install();
  await page.addInitScript(({ snapshot, eventName, options }) => {
    let sequence = 0;
    const callbacks = new Map<number, (event: unknown) => void>();
    const listeners = new Map<number, { event: string; handler: number }>();
    const openers: Array<{ resolve: () => void; reject: () => void }> = [];
    const calls: UpdatesWindow["__updatesCalls"] = [];
    const versions: Array<(version: string) => void> = [];
    let holdVersion = options.holdVersion;
    Object.assign(window, {
      isTauri: true,
      __updatesCalls: calls,
      __updatesState: { state: "idle" },
      __updatesListeners: () => [...listeners.values()].filter((entry) => entry.event === eventName).length,
      __updatesMenu: () => {
        for (const [id, entry] of listeners) {
          if (entry.event === eventName) callbacks.get(entry.handler)?.({ event: eventName, id, payload: null });
        }
      },
      __updatesResolveOpen: (index: number) => openers[index].resolve(),
      __updatesRejectOpen: (index: number) => openers[index].reject(),
      __updatesResolveVersion: () => { holdVersion = false; for (const resolve of versions) resolve(options.version ?? "3.8.39"); },
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: (_event: string, id: number) => listeners.delete(id) },
      __TAURI_INTERNALS__: {
        transformCallback: (callback: (event: unknown) => void) => { const id = ++sequence; callbacks.set(id, callback); return id; },
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          calls.push({ command, args });
          if (command === "plugin:event|listen") {
            const id = ++sequence;
            listeners.set(id, { event: String(args.event), handler: Number(args.handler) });
            return id;
          }
          if (command === "plugin:event|unlisten") return;
          if (command === "plugin:app|version") return holdVersion ? new Promise<string>((resolve) => versions.push(resolve)) : options.version ?? "3.8.39";
          if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
          if (command === "desktop_preparation_status") return true;
          if (command === "desktop_update_status") return (window as UpdatesWindow).__updatesState;
          if (command === "desktop_update_download") {
            const current = { id: "update-test", version: String(args.version), tag: String(args.tag),
              asset_name: String(args.assetName), asset_bytes: Number(args.assetBytes), received_bytes: 20_000, state: "downloading" };
            (window as UpdatesWindow).__updatesState = current;
            return new Promise((resolve, reject) => {
              (window as UpdatesWindow).__updatesRejectDownload = () => reject("update_download_failed");
              (window as UpdatesWindow).__updatesCompleteDownload = () => {
                const ready = { ...current, state: "ready", received_bytes: current.asset_bytes };
                (window as UpdatesWindow).__updatesState = ready;
                resolve(ready);
              };
            });
          }
          if (command === "desktop_update_install") return { id: args.updateId, state: "awaiting_health" };
          if (command === "desktop_update_target") return { platform: "macos", arch: "arm64" };
          if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
          if (command === "desktop_open_releases") return new Promise<void>((resolve, reject) => openers.push({ resolve, reject: () => reject(new Error("mock opener failed")) }));
          throw new Error(`Unexpected update test IPC: ${command}`);
        },
      },
    });
  }, { snapshot, eventName: DESKTOP_UPDATE_EVENT, options });
  const name = "Simplicio-3.8.40-arm64.dmg";
  await page.route((url) => url.href === DESKTOP_RELEASES_API, (route) => route.fulfill({
    status: 200, headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
    body: JSON.stringify([{ tag_name: "v3.8.40", draft: false, prerelease: false, html_url: `${DESKTOP_RELEASES_URL}/tag/v3.8.40`,
      published_at: "2026-08-31T01:34:29Z", body: options.notes ?? "Melhorias no login e nas integrações do Desktop.",
      assets: [{ name, state: "uploaded", size: 100_000, browser_download_url: `${DESKTOP_RELEASES_URL}/download/v3.8.40/${name}` }],
    }]),
  }));
  await page.goto("/");
  await expect.poll(() => page.evaluate(() => (window as UpdatesWindow).__updatesListeners())).toBe(1);
}

test("General settings opens the same updater without starting a download", async ({ page }) => {
  await mockUpdates(page);
  await page.goto("/?view=general-settings");
  await page.getByRole("button", {name:"Verificar atualizações do Desktop", exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
  const effects = await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter(call => ["desktop_update_download", "desktop_update_install"].includes(call.command)));
  expect(effects).toEqual([]);
});

async function showUpdates(page: Page) {
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
}

async function openerCalls(page: Page) {
  return page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter((entry) => entry.command === "desktop_open_releases"));
}

test("pending release opener times out honestly and ignores late completion after an explicit retry (mocked IPC)", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await expect(page.getByRole("dialog")).toContainText("Versão deste aplicativo: 3.8.39");
  const subscriptions = await page.evaluate((eventName) => (window as UpdatesWindow).__updatesCalls.filter((entry) => entry.command === "plugin:event|listen" && entry.args.event === eventName), DESKTOP_UPDATE_EVENT);
  expect(subscriptions.every((entry) => JSON.stringify(entry.args.target) === JSON.stringify({ kind: "AnyLabel", label: "main" }))).toBe(true);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).dblclick();
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  expect(await openerCalls(page)).toEqual([{ command: "desktop_open_releases", args: {} }]);

  await page.clock.fastForward(8_001);
  await expect(page.getByRole("alert")).toContainText("Não foi possível confirmar a abertura; confira o navegador.");
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  expect(await openerCalls(page)).toHaveLength(1);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).click();
  expect(await openerCalls(page)).toHaveLength(2);
  await page.evaluate(() => (window as UpdatesWindow).__updatesResolveOpen(0));
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  await page.evaluate(() => (window as UpdatesWindow).__updatesResolveOpen(1));
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("closing a pending opener preserves uncertainty on reopen and ignores its late rejection (mocked IPC)", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).click();
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Fechar atualizações", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await showUpdates(page);
  await expect(page.getByRole("alert")).toContainText("A tentativa anterior ainda pode concluir.");
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  await page.evaluate(() => (window as UpdatesWindow).__updatesRejectOpen(0));
  await expect(page.getByRole("alert")).toContainText("A tentativa anterior ainda pode concluir.");
  await page.clock.fastForward(8_001);
  await expect(page.getByRole("alert")).toContainText("Uma nova tentativa só será feita se você clicar novamente.");
  expect(await openerCalls(page)).toEqual([{ command: "desktop_open_releases", args: {} }]);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
});

test("shows a white native-update dialog and public release notes only as inert text (mocked IPC/metadata)", async ({ page }, testInfo) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  const notes = "## Mudanças\n<img src='https://untrusted.invalid/pixel' onerror='alert(1)'>\n[Download](javascript:alert(1))\n<script>alert(1)</script>";
  await mockUpdates(page, { notes });
  await showUpdates(page);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(dialog).toContainText("Atualização verificada pela distribuição");
  await expect(dialog.getByRole("button", { name: "Baixar e verificar" })).toBeEnabled();
  await expect(dialog).toContainText("97,7 KiB");
  await expect(dialog.locator("time")).toHaveAttribute("datetime", "2026-08-31T01:34:29Z");
  await expect(dialog.locator("time")).toHaveText("31/08/2026");
  await page.screenshot({ path: testInfo.outputPath("updates-available.png") });
  await dialog.locator("summary").click();
  await expect(dialog.locator("pre")).toHaveText(notes);
  await expect(dialog.locator("a, script, iframe")).toHaveCount(0);
  await expect(dialog.locator("img")).toHaveCount(1);
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  expect(requests.filter((url) => url === DESKTOP_RELEASES_API)).toHaveLength(1);
  expect(requests.some((url) => url.includes("untrusted.invalid") || url.includes("/releases/download/"))).toBe(false);
  expect(await openerCalls(page)).toHaveLength(0);
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeInViewport({ ratio: 1 });
  await page.screenshot({ path: testInfo.outputPath("updates-notes-escaped.png") });
});

test("keeps real progress cancelable, traps focus and ignores a late local identity response (mocked IPC)", async ({ page }, testInfo) => {
  const requests: string[] = [];
  page.on("request", (request) => { if (request.url() === DESKTOP_RELEASES_API) requests.push(request.url()); });
  await mockUpdates(page, { holdVersion: true });
  const origin = page.getByRole("button").first();
  await origin.focus();
  await page.evaluate(() => { (window as UpdatesWindow).__updatesMenu(); (window as UpdatesWindow).__updatesMenu(); });
  const dialog = page.getByRole("dialog");
  await expect(dialog).toHaveAttribute("data-update-state", "checking");
  await expect(dialog.locator("[data-update-stage]")).toHaveAttribute("data-update-stage", "identity");
  await expect(dialog).toContainText("O instalador não está sendo baixado.");
  await expect(page.getByRole("progressbar", { name: "Progresso da consulta de atualização" })).not.toHaveAttribute("value", /.*/);
  await expect(page.getByRole("button", { name: "Fechar atualizações", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Cancelar consulta", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: "Fechar atualizações", exact: true })).toBeFocused();
  const versionCalls = await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter((entry) => entry.command === "plugin:app|version"));
  expect(versionCalls).toHaveLength(1);
  await page.screenshot({ path: testInfo.outputPath("updates-checking.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(origin).toBeFocused();
  await page.evaluate(() => (window as UpdatesWindow).__updatesResolveVersion());
  await page.clock.fastForward(1);
  await expect(dialog).toHaveCount(0);
  expect(requests).toHaveLength(0);
  await showUpdates(page);
  expect(requests).toHaveLength(1);
});

test("a stalled metadata request times out without fake success or automatic retries (mocked IPC/metadata)", async ({ page }) => {
  await mockUpdates(page);
  const held: Route[] = [];
  const matchesApi = (url: URL) => url.href === DESKTOP_RELEASES_API;
  const hold = (route: Route) => { held.push(route); };
  await page.route(matchesApi, hold);
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog").locator("[data-update-stage]")).toHaveAttribute("data-update-stage", "requesting");
  await expect.poll(() => held.length).toBe(1);
  await page.clock.fastForward(15_001);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "error");
  await expect(page.getByRole("dialog")).toContainText("A consulta excedeu o tempo limite");
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await page.clock.fastForward(20_000);
  expect(held).toHaveLength(1);
  expect(await openerCalls(page)).toHaveLength(0);
  await page.unroute(matchesApi, hold);
  // The browser may already have canceled the held route. Either way it cannot update the UI.
  await held[0].fulfill({ status: 200, headers: { "content-type": "application/json", "access-control-allow-origin": "*" }, body: "[]" }).catch(() => undefined);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "error");
  await page.getByRole("button", { name: "Verificar novamente", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
});

test("an invalid installed version stays unknown without querying release metadata (mocked IPC)", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => { if (request.url() === DESKTOP_RELEASES_API) requests.push(request.url()); });
  await mockUpdates(page, { version: "latest" });
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "error");
  await expect(page.getByRole("dialog")).toContainText("O aplicativo não informou uma versão válida");
  await expect(page.getByRole("dialog")).not.toContainText("Simplicio está atualizado");
  expect(requests).toHaveLength(0);
});

test("offline checks remain unknown and only retry after the user reconnects and clicks (mocked IPC)", async ({ page, context }) => {
  await mockUpdates(page);
  await context.setOffline(true);
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "offline");
  await expect(page.getByRole("dialog")).toContainText("Sem conexão de rede");
  await context.setOffline(false);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "offline");
  await page.getByRole("button", { name: "Verificar novamente", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
});

test("background check offers a dismissible notice without opening a modal or downloading", async ({ page }) => {
  await mockUpdates(page);
  await page.clock.fastForward(5_001);
  const notice = page.getByRole("status", { name: "Atualização disponível", exact: true });
  await expect(notice).toContainText("Simplicio 3.8.40 disponível");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter(call => call.command === "desktop_update_download"))).toHaveLength(0);
  await notice.getByRole("button", { name: "Ver atualização" }).click();
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
});

test("download failure stays visible across stale polling and can explicitly resume", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await page.getByRole("button", { name: "Baixar e verificar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Baixando atualização…" })).toBeVisible();
  await page.clock.fastForward(1_501);
  await expect(page.getByRole("progressbar", { name: "Progresso do download" })).toHaveAttribute("value", "20");
  await page.evaluate(() => (window as UpdatesWindow).__updatesRejectDownload());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-action", "error");
  await page.clock.fastForward(6_001);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-action", "error");
  await expect(page.getByRole("alert")).toContainText("O download falhou");
  await page.getByRole("button", { name: "Retomar download", exact: true }).click();
  await page.evaluate(() => (window as UpdatesWindow).__updatesCompleteDownload());
  await expect(page.getByRole("heading", { name: "Atualização pronta para instalar" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Instalar e reiniciar", exact: true })).toBeEnabled();
});

test("closing and reopening during a download cannot duplicate its effect", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await page.getByRole("button", { name: "Baixar e verificar", exact: true }).click();
  await page.getByRole("button", { name: "Fechar atualizações", exact: true }).click();
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-action", "downloading");
  await expect(page.getByRole("button", { name: "Verificar novamente" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Baixar e verificar", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter(call => call.command === "desktop_update_download"))).toHaveLength(1);
  await page.evaluate(() => (window as UpdatesWindow).__updatesCompleteDownload());
  await page.getByRole("button", { name: "Instalar e reiniciar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Confirmando reinicialização" })).toBeVisible();
  expect(await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter(call => call.command === "desktop_update_install"))).toEqual([{ command: "desktop_update_install", args: { updateId: "update-test" } }]);
});

test("polling never promotes a package from another release to installable", async ({ page }) => {
  await mockUpdates(page);
  await page.evaluate(() => {
    (window as UpdatesWindow).__updatesState = {
      id: "old-package", state: "ready", version: "3.8.38", tag: "v3.8.38",
      asset_name: "Simplicio-3.8.38-arm64.dmg", asset_bytes: 100_000, received_bytes: 100_000,
    };
  });
  await showUpdates(page);
  await page.clock.fastForward(3_001);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-action", "idle");
  await expect(page.getByRole("button", { name: "Instalar e reiniciar" })).toHaveCount(0);
});
