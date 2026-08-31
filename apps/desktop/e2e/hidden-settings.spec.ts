import { expect, test } from "@playwright/test";

const hidden = [
  "Agentes e IDEs", "Modelos e skills", "Artefatos", "Automações",
  "Orquestração", "Uso do computador", "Voz", "Integrações de serviços", "Simplicio Mobile",
  "Memória", "Compartilhar skills", "Git e código-fonte", "Fontes de tarefas", "Terminal", "Navegador",
  "Emulador mobile", "Janela flutuante", "Atalhos", "Entrada e edição", "Notificações",
  "Hosts SSH", "Servidores Simplicio", "Privacidade e telemetria", "Avançado", "Experimental", "Plugins",
];

test("requested settings are absent from categories and both search surfaces", async ({ page }, testInfo) => {
  await page.goto("/?view=settings");
  const sidebar = page.locator("#workbench-sidebar");
  const categories = sidebar.getByRole("navigation");
  for (const label of hidden) await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  for (const group of ["HOSTS REMOTOS", "EXPERIMENTAL"]) await expect(categories.getByText(group, { exact: true })).toHaveCount(0);
  for (const label of ["Contas de IA", "Geral", "Comandos rápidos", "Aparência", "Permissões do sistema", "Runtime e diagnóstico", "Integrações MCP", "Relatório de tokens"])
    await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(1);
  await expect(sidebar.getByRole("button", { name: "Ver atalhos", exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("visible-settings.png") });
  for (const label of hidden) {
    await sidebar.getByRole("searchbox").fill(label);
    await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
  await page.goto("/");
  for (const label of ["Agentes e IDEs", "Automações"]) {
    await expect(sidebar.getByRole("button", { name: label, exact: true })).toHaveCount(0);
    await expect(page.getByRole("main").getByRole("button", { name: new RegExp(label) })).toHaveCount(0);
  }
  await expect(page.getByRole("main").getByRole("button", { name: /Tokens e economia/ })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("visible-home.png") });
  await expect(page.getByRole("button", { name: "Todos os atalhos", exact: true })).toHaveCount(0);
  for (const label of hidden) {
    await sidebar.getByRole("searchbox").fill(label);
    await expect(sidebar.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
});

test("visible reference pages do not expose links back to hidden destinations", async ({ page }) => {
  for (const view of ["provider-accounts", "general-settings", "quick-commands", "permissions"]) {
    await page.goto("/?view=" + view);
    await expect(page.locator(".reference-settings-page")).toBeVisible();
    await expect(page.getByRole("main").getByRole("button", { name: /Ver atalhos|Abrir atalhos|Abrir navegador|Abrir terminal|Configurar voz|Ver agente e IDE/ })).toHaveCount(0);
  }
});

test("narrow navigation and account pages keep requested destinations hidden", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 740 });
  await page.goto("/");
  await page.getByRole("button", { name: "Expandir barra lateral", exact: true }).click();
  const workspaceMenu = page.getByRole("dialog", { name: "Espaço de trabalho", exact: true });
  await expect(workspaceMenu).toBeVisible();
  for (const label of hidden) {
    await workspaceMenu.getByRole("searchbox").fill(label);
    await expect(workspaceMenu.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
  await workspaceMenu.getByRole("searchbox").fill("");
  await workspaceMenu.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Conta Simplicio", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: "Expandir barra lateral", exact: true }).click();
  const settingsMenu = page.getByRole("dialog", { name: "Configurações", exact: true });
  const categories = settingsMenu.getByRole("navigation", { name: "Categorias de configurações", exact: true });
  for (const label of hidden) await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  for (const group of ["HOSTS REMOTOS", "EXPERIMENTAL"]) await expect(categories.getByText(group, { exact: true })).toHaveCount(0);
  for (const label of hidden) {
    await settingsMenu.getByRole("searchbox").fill(label);
    await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
  await settingsMenu.getByRole("searchbox").fill("");
  await categories.getByRole("button", { name: "Contas de IA", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Contas de IA", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("main").getByRole("button", { name: "Ver agente e IDE", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Abrir conta Simplicio", exact: true })).toBeVisible();
});
