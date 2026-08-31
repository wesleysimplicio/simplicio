import { expect, test } from "@playwright/test";

test("workbench navigation, settings search, history and sidebar controls work", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Atividade", exact: true }).click();
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Conta Simplicio" })).toBeVisible();
  await page.getByRole("button", { name: "Voltar ao app" }).click();
  await expect(page.getByRole("heading", { name: "Atividade", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Voltar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Conta Simplicio" })).toBeVisible();
  await page.getByRole("button", { name: "Avançar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Atividade", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByRole("searchbox", { name: "Buscar configurações" }).fill("aparencia");
  await page.getByRole("button", { name: "Aparência", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aparência", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Compacta", exact: true }).click();
  await page.getByRole("switch", { name: "Mostrar caminhos na lateral" }).click();
  await page.reload();
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByRole("button", { name: "Aparência", exact: true }).click();
  await expect(page.getByRole("button", { name: "Compacta", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("switch", { name: "Mostrar caminhos na lateral" })).toHaveAttribute("aria-checked", "true");
  await expect(page.locator(".workbench")).toHaveAttribute("data-density", "compact");

  await page.getByRole("button", { name: "Recolher barra lateral" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/sidebar-collapsed/);
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("searchbox", { name: "Buscar configurações" })).toBeFocused();
  await page.keyboard.type("nenhum-resultadoteste");
  await expect(page.getByText("Nenhum resultado.")).toBeVisible();
  await page.getByRole("button", { name: "Limpar busca", exact: true }).click();
  await page.getByRole("button", { name: "Comandos rápidos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Comandos rápidos", exact: true })).toBeVisible();
});

test("provider inventory is searchable and never upgrades detected to connected", async ({ page }) => {
  await page.goto("/?view=agents");
  await page.getByRole("searchbox", { name: "Buscar agentes e IDEs" }).fill("codex");
  await expect(page.locator(".provider-list-row")).toHaveCount(1);
  await page.getByRole("button", { name: /Ver detalhes de .*Codex/ }).click();
  await expect(page.locator(".provider-row-detail")).toContainText("Não verificado");
  await page.getByRole("searchbox", { name: "Buscar agentes e IDEs" }).fill("nonexistent-provider");
  await expect(page.getByText("Nenhum cliente neste filtro")).toBeVisible();
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  expect(await page.locator(".provider-list-row").count()).toBeGreaterThan(1);
  await page.getByRole("combobox", { name: "Tipo de cliente" }).selectOption("editor");
  for (const row of await page.locator(".provider-list-copy").all()) await expect(row).toContainText("IDE / ADE");
});

test("browser preview never claims to validate local folders", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await page.getByLabel("Caminho da pasta").fill("/tmp/project");
  await page.getByRole("dialog").getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("demonstração no navegador não acessa seus arquivos");
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
