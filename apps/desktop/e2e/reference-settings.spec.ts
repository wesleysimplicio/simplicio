import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import type { DesktopSnapshot } from "../src/contracts";

type SettingsTestWindow = Window & {
  __referenceCalls: string[];
  __referenceCopies: string[];
  __referenceResolveCopy: (index: number) => void;
};

const referenceViews = [
  { id: "computer-use", heading: "Uso do computador" },
  { id: "voice", heading: "Voz" },
  { id: "mobile", heading: "Simplicio Mobile" },
  { id: "plugins", heading: "Plugins" },
  { id: "permissions", heading: "Permissões do sistema" },
];

async function mockReadonlyRuntime(page: Page, snapshot: DesktopSnapshot) {
  await page.addInitScript((snapshot) => {
    let callbackId = 0;
    const calls: string[] = [];
    Object.assign(window, {
      isTauri: true,
      __referenceCalls: calls,
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: () => {} },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++callbackId,
        invoke: async (command: string) => {
          calls.push(command);
          if (command === "plugin:event|listen") return ++callbackId;
          if (command === "plugin:event|unlisten") return;
          if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
          throw new Error("Unexpected readonly settings IPC: " + command);
        },
      },
    });
  }, snapshot);
}

function runtimeFixture() {
  const snapshot = structuredClone(createDemoSnapshot("active"));
  snapshot.source = "runtime";
  if (snapshot.botCenter) snapshot.botCenter.source = "runtime";
  return snapshot;
}

async function mockClipboard(page: Page) {
  await page.addInitScript(() => {
    const copies: string[] = [];
    const pending: Array<() => void> = [];
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: (text: string) => {
          copies.push(text);
          return new Promise<void>((resolve) => pending.push(resolve));
        },
      },
    });
    Object.assign(window, {
      __referenceCopies: copies,
      __referenceResolveCopy: (index: number) => pending[index](),
    });
  });
}

test("reference capability surfaces are white, distinct, and honest about unavailable effects (preview)", async ({ page }, testInfo) => {
  const unexpected: string[] = [];
  page.on("request", (request) => {
    if (!/^https?:\/\/127\.0\.0\.1:\d+\//.test(request.url())) unexpected.push(request.url());
  });
  for (const view of referenceViews) {
    await page.goto("/?view=" + view.id);
    const panel = page.locator(".reference-settings-page");
    await expect(panel.getByRole("heading", { name: view.heading, exact: true, level: 1 })).toBeVisible();
    await expect(panel).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(panel).toContainText("Prévia visual.");
    expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("reference-" + view.id + "-white.png") });
  }
  await expect(page.getByRole("button", { name: "Solicitar microfone", exact: true })).toBeDisabled();
  await page.goto("/?view=voice");
  await expect(page.getByRole("switch", { name: "Ativar ditado por voz", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "Modelo de voz", exact: true })).toBeDisabled();
  await page.goto("/?view=mobile");
  await expect(page.getByRole("button", { name: "Gerar QR code", exact: true })).toBeDisabled();
  await expect(page.locator(".ref-pairing-empty")).toContainText("Nenhum código emitido");
  await expect(page.locator(".ref-pairing-empty img, .ref-pairing-empty canvas")).toHaveCount(0);
  expect(unexpected).toEqual([]);
});

test("reference settings preserve readable controls in a narrow white window (preview)", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 740 });
  for (const view of referenceViews) {
    await page.goto("/?view=" + view.id);
    const panel = page.locator(".reference-settings-page");
    await expect(panel.getByRole("heading", { name: view.heading, exact: true, level: 1 })).toBeVisible();
    await expect(panel).toHaveCSS("background-color", "rgb(255, 255, 255)");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("reference-" + view.id + "-narrow.png") });
  }
});

test("plugin catalog search and evidence tabs work without pretending packages are installed (preview)", async ({ page }) => {
  await page.goto("/?view=plugins");
  const panel = page.locator(".reference-settings-page");
  const search = panel.getByRole("searchbox", { name: "Buscar plugins e skills", exact: true });
  await expect(panel.locator(".ref-plugin-card")).toHaveCount(5);
  await search.fill("hermes");
  await expect(panel.locator(".ref-plugin-card")).toHaveCount(1);
  await expect(panel.getByRole("heading", { name: "Simplicio Hermes", exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Instalar Simplicio Hermes", exact: true })).toBeDisabled();
  await search.fill("pacote-que-nao-existe");
  await expect(panel.getByRole("heading", { name: "Nenhum resultado neste filtro", exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Limpar busca", exact: true }).click();
  await expect(search).toHaveValue("");
  await panel.getByRole("button", { name: "Skills informadas", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Skills informadas", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(panel.getByRole("heading", { name: "Nenhuma skill informada nesta consulta", exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Catálogo público", exact: true }).click();
  await expect(panel.locator(".ref-plugin-card")).toHaveCount(5);
  await panel.getByRole("button", { name: "Revisar plano MCP", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Integrações MCP", exact: true, level: 1 })).toBeVisible();
});

test("read-only evidence is escaped and refresh never dispatches unsupported setup actions (mocked IPC)", async ({ page }) => {
  const snapshot = runtimeFixture();
  const malicious = '<img src="https://example.test/secret" onerror="alert(1)">';
  snapshot.access.email = "private-person@example.test";
  snapshot.providers[0].detail = "private-configuration-body";
  snapshot.botCenter!.bots[0].displayName = malicious;
  snapshot.botCenter!.bots[0].skills = ["Skill de teste", malicious];
  snapshot.botCenter!.computer.available = true;
  await mockReadonlyRuntime(page, snapshot);
  const external: string[] = [];
  page.on("request", (request) => { if (request.url().startsWith("https://example.test/")) external.push(request.url()); });
  await page.goto("/?view=orchestration");
  const panel = page.locator(".reference-settings-page");
  await expect(panel.getByText(malicious, { exact: true })).toBeVisible();
  await expect(panel.locator("img, iframe, script")).toHaveCount(0);
  await expect(panel).not.toContainText("private-person@example.test");
  await expect(panel).not.toContainText("private-configuration-body");
  const sidebar = page.getByRole("complementary", { name: "Configurações", exact: true });
  await sidebar.getByRole("button", { name: "Plugins", exact: true }).click();
  await panel.getByRole("button", { name: "Skills informadas", exact: true }).click();
  await expect(panel.getByText("Skill de teste", { exact: true })).toBeVisible();
  await expect(panel.getByText(malicious, { exact: true })).toBeVisible();
  await sidebar.getByRole("button", { name: "Permissões do sistema", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Solicitar microfone", exact: true })).toBeDisabled();
  await panel.getByRole("button", { name: "Solicitar microfone", exact: true }).evaluate((button) => (button as HTMLButtonElement).click());
  await panel.getByRole("button", { name: "Atualizar consulta do Runtime", exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as SettingsTestWindow).__referenceCalls.filter((command) => command === "refresh_desktop_snapshot").length)).toBe(1);
  const calls = await page.evaluate(() => (window as SettingsTestWindow).__referenceCalls);
  expect(calls.every((command) => ["desktop_snapshot", "refresh_desktop_snapshot", "plugin:event|listen", "plugin:event|unlisten"].includes(command))).toBe(true);
  expect(external).toEqual([]);
});

test("command copy has a finite wait, no automatic retry, and no late success claim (mocked clipboard)", async ({ page }) => {
  await page.clock.install();
  await mockClipboard(page);
  await page.goto("/?view=quick-commands");
  const button = page.getByRole("button", { name: "Copiar Versão do Runtime", exact: true });
  await button.click();
  await expect(button).toBeDisabled();
  await button.evaluate((element) => (element as HTMLButtonElement).click());
  expect(await page.evaluate(() => (window as SettingsTestWindow).__referenceCopies)).toEqual(["simplicio version"]);
  await page.clock.fastForward(4001);
  await expect(page.getByRole("status").filter({ hasText: "Não foi possível confirmar a cópia." })).toBeVisible();
  await expect(button).toBeEnabled();
  await page.clock.fastForward(4001);
  expect(await page.evaluate(() => (window as SettingsTestWindow).__referenceCopies)).toHaveLength(1);
  await button.click();
  await page.evaluate(() => (window as SettingsTestWindow).__referenceResolveCopy(0));
  await expect(button).toHaveText("Copiando…");
  await expect(button).toBeDisabled();
  await page.evaluate(() => (window as SettingsTestWindow).__referenceResolveCopy(1));
  await expect(button).toHaveText("Copiado");
  await expect(page.getByRole("status").filter({ hasText: "Comando copiado. Nenhum comando foi executado." })).toBeVisible();
});

test("leaving a pending copy ignores its completion and does not carry a spinner into the next visit", async ({ page }) => {
  await mockClipboard(page);
  await page.goto("/?view=quick-commands");
  const copy = page.getByRole("button", { name: "Copiar Versão do Runtime", exact: true });
  await copy.click();
  await expect(copy).toBeDisabled();
  const sidebar = page.getByRole("complementary", { name: "Configurações", exact: true });
  await sidebar.getByRole("button", { name: "Voz", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Voz", exact: true, level: 1 })).toBeVisible();
  await page.evaluate(() => (window as SettingsTestWindow).__referenceResolveCopy(0));
  await expect(page.locator(".reference-settings-page")).not.toContainText("Copiado");
  await sidebar.getByRole("button", { name: "Comandos rápidos", exact: true }).click();
  await expect(copy).toBeEnabled();
  await expect(copy).toHaveText("Copiar");
  expect(await page.evaluate(() => (window as SettingsTestWindow).__referenceCopies)).toHaveLength(1);
});

test("task source details are keyboard-operable without saving a fake connection preference", async ({ page }) => {
  await page.goto("/?view=task-sources");
  const summary = page.locator(".ref-source-details summary").filter({ hasText: "Linear" });
  await summary.focus();
  await page.keyboard.press("Enter");
  const details = page.locator(".ref-source-details").filter({ has: page.locator("summary").filter({ hasText: "Linear" }) });
  await expect(details).toHaveAttribute("open", "");
  await expect(details.getByRole("switch", { name: "Mostrar tarefas de Linear", exact: true })).toBeDisabled();
  await details.getByRole("button", { name: "Ver conexão do serviço", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Integrações de serviços", exact: true, level: 1 })).toBeVisible();
});
