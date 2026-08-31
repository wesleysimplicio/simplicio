import { expect, test } from "@playwright/test";

const hidden = [
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
  for (const label of ["Contas de IA", "Geral", "Artefatos", "Comandos rápidos", "Aparência", "Permissões do sistema", "Runtime e diagnóstico", "Integrações MCP", "Relatório de tokens"])
    await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(1);
  await expect(sidebar.getByRole("button", { name: "Ver atalhos", exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("visible-settings.png") });
  for (const label of hidden) {
    await sidebar.getByRole("searchbox").fill(label);
    await expect(categories.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Todos os atalhos", exact: true })).toHaveCount(0);
  for (const label of hidden) {
    await sidebar.getByRole("searchbox").fill(label);
    await expect(sidebar.getByRole("button", { name: label, exact: true })).toHaveCount(0);
  }
});

test("visible reference pages do not expose links back to hidden destinations", async ({ page }) => {
  for (const view of ["provider-accounts", "general-settings", "artifacts", "quick-commands", "permissions"]) {
    await page.goto("/?view=" + view);
    await expect(page.locator(".reference-settings-page")).toBeVisible();
    await expect(page.getByRole("main").getByRole("button", { name: /Ver atalhos|Abrir atalhos|Abrir navegador|Abrir terminal|Configurar voz/ })).toHaveCount(0);
  }
});
