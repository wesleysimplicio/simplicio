import { expect, test } from "@playwright/test";
import { REFERENCE_SCREENS } from "../src/reference_screens";
import { isNavigationVisible } from "../src/workbench";

const visibleScreens = REFERENCE_SCREENS.filter((screen) => isNavigationVisible(screen.id));

test("every supplied-reference settings destination is searchable and reachable without losing navigation", async ({ page }, testInfo) => {
  await page.goto("/?view=settings");
  const sidebar = page.getByRole("complementary", { name: "Configurações", exact: true });
  const categories = sidebar.getByRole("navigation", { name: "Categorias de configurações", exact: true });
  const search = sidebar.getByRole("searchbox", { name: "Buscar configurações", exact: true });
  for (const screen of visibleScreens) await expect(categories.getByRole("button", { name: screen.label, exact: true })).toHaveCount(1);
  expect(await page.locator(".sidebar-scroll").evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  await expect(sidebar.getByRole("button", { name: "Voltar ao app", exact: true })).toBeInViewport();
  await expect(sidebar.getByRole("button", { name: "Configurações", exact: true })).toBeInViewport();

  for (const screen of visibleScreens) {
    await search.fill(screen.label);
    await categories.getByRole("button", { name: screen.label, exact: true }).click();
    await expect(page.getByRole("heading", { name: screen.label, exact: true, level: 1 })).toBeVisible();
    await expect(categories.getByRole("button", { name: screen.label, exact: true })).toHaveAttribute("aria-current", "page");
    await expect(categories.getByRole("button", { name: screen.label, exact: true })).toBeInViewport();
    await expect(search).toHaveValue("");
  }
  await expect(sidebar.getByRole("button", { name: "Voltar ao app", exact: true })).toBeInViewport();
  await expect(sidebar.getByRole("button", { name: "Configurações", exact: true })).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath("reference-settings-navigation.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("reference navigation is discoverable by description and usable in a narrow window", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 740 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true, level: 1 })).toBeVisible();
  await page.keyboard.press("Control+k");
  const workspaceMenu = page.getByRole("dialog", { name: "Espaço de trabalho", exact: true });
  await workspaceMenu.getByRole("searchbox").fill("comandos documentados");
  const mobile = workspaceMenu.getByRole("button", { name: "Comandos rápidos", exact: true });
  await expect(mobile).toBeVisible();
  await mobile.click();
  await expect(page.getByRole("heading", { name: "Comandos rápidos", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: "Expandir barra lateral", exact: true }).click();
  const settingsMenu = page.getByRole("dialog", { name: "Configurações", exact: true });
  await settingsMenu.getByRole("searchbox").fill("Permissões do sistema");
  await settingsMenu.getByRole("button", { name: "Permissões do sistema", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Permissões do sistema", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("reference-narrow-settings.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the main sidebar exposes the existing automation surface", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Navegação principal", exact: true }).getByRole("button", { name: "Automações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Automações", exact: true, level: 1 })).toBeVisible();
});
