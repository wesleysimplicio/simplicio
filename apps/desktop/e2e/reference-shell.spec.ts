import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

test("narrow navigation overlays the workspace and keeps keyboard focus inside until dismissed", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 740 });
  await page.goto("/");
  await expect(page.getByRole("contentinfo", { name: "Estado do Simplicio", exact: true }).getByText("Demonstração", { exact: true })).toBeVisible();
  const content = page.getByRole("main");
  const initialWidth = (await content.boundingBox())?.width;
  expect(initialWidth).toBeGreaterThan(300);
  const expand = page.getByRole("button", { name: "Expandir barra lateral", exact: true });
  await expand.click();
  await expect.poll(async () => (await content.boundingBox())?.width).toBe(initialWidth);
  const drawer = page.getByRole("dialog", { name: "Espaço de trabalho", exact: true });
  await expect(drawer).toHaveAttribute("aria-modal", "true");
  await expect(drawer.getByText("Simplicio", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Atividade", { exact: true })).toBeVisible();
  await expect(drawer.getByRole("searchbox")).toBeFocused();
  await expect(page.locator(".workspace")).toHaveAttribute("inert", "");
  await page.screenshot({ path: testInfo.outputPath("narrow-navigation.png") });

  await drawer.getByRole("button", { name: "Início do Simplicio", exact: true }).focus();
  await page.keyboard.press("Shift+Tab");
  await expect(drawer.getByRole("button", { name: "Configurações", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(drawer.getByRole("button", { name: "Início do Simplicio", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(expand).toBeFocused();
  await expect(page.locator(".workspace")).not.toHaveAttribute("inert", "");

  await page.keyboard.press("Control+k");
  const search = drawer.getByRole("searchbox");
  await expect(search).toBeFocused();
  await search.fill("Atividade");
  await search.press("ArrowDown");
  await expect(drawer.getByRole("button", { name: "Atividade", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(drawer).toHaveCount(0);
  await expect(content.getByRole("heading", { name: "Atividade", exact: true })).toBeVisible();
  await expect(content).toBeFocused();

  await expand.click();
  await page.getByRole("button", { name: "Fechar navegação", exact: true }).click({ position: { x: 374, y: 240 } });
  await expect(drawer).toHaveCount(0);
  await expect(expand).toBeFocused();

  await expand.click();
  await drawer.getByRole("button", { name: "Adicionar projeto à lista", exact: true }).click();
  await expect(drawer).toHaveCount(0);
  const projectDialog = page.getByRole("dialog", { name: "Adicionar projeto", exact: true });
  await expect(projectDialog.getByRole("button", { name: "Escolher pasta…", exact: true })).toBeFocused();
  await projectDialog.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Adicionar projeto à lista", exact: true })).toBeFocused();
});

test("the workbench supports skipping navigation and collapses safely when resized", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true, level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Ir para o conteúdo", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();

  await page.setViewportSize({ width: 768, height: 700 });
  await expect(page.getByRole("complementary", { name: "Espaço de trabalho" }).getByText("Atividade", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 720, height: 700 });
  await expect(page.getByRole("button", { name: "Expandir barra lateral", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Espaço de trabalho" })).toBeVisible();
  await expect(page.locator(".workspace")).not.toHaveAttribute("inert", "");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the status bar separates configuration records from confirmed MCP connections (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  snapshot.providers = snapshot.providers.slice(0, 2).map((provider) => ({
    ...provider, state: "connected", installState: "installed", registrationState: "registered",
    handshakeState: "unverified", freshness: "current",
  }));
  await page.addInitScript((snapshot) => {
    Object.assign(window, { __TAURI_INTERNALS__: { invoke: async (command: string) => {
      if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
      if (command === "plugin:event|listen") return 1;
      if (command === "plugin:event|unlisten") return;
      throw "unexpected_reference_status_command";
    } } });
  }, snapshot);
  await page.goto("/");
  const status = page.getByRole("contentinfo", { name: "Estado do Simplicio", exact: true });
  await expect(status).toContainText("0 MCP confirmados");
  await expect(status).toContainText("2 registros detectados");
  await expect(status).not.toContainText("MCP ativos");
  const connection = status.getByRole("button", { name: /0 MCP confirmados/ });
  await expect(connection).toHaveAttribute("title", /não prova que o cliente está desconectado/);
  await connection.click();
  await expect(page.getByRole("heading", { name: "Integrações MCP", exact: true })).toBeVisible();
});
