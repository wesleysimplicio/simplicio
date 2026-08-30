import { expect, test } from "@playwright/test";

test("login and conservative access states remain actionable", async ({ page }) => {
  await page.goto("/?state=signed_out");
  await expect(page.getByRole("heading", { name: "Entre no Simplicio" })).toBeVisible();
  await page.getByRole("button", { name: /Continuar com Google/ }).click();
  await expect(page.getByRole("heading", { name: "Hoje você economizou." })).toBeVisible();

  await page.goto("/?state=unknown");
  await expect(page.getByRole("heading", { name: "Tente novamente" })).toBeVisible();
  await page.getByRole("button", { name: "Abrir diagnóstico" }).click();
  await expect(page.getByText("nenhuma cobrança ou assinatura foi alterada")).toBeVisible();
  await page.getByRole("button", { name: "Fechar diagnóstico" }).click();
  await expect(page.getByText("nenhuma cobrança ou assinatura foi alterada")).toBeHidden();

  await page.goto("/?state=inactive");
  await expect(page.getByRole("heading", { name: "Ative o Simplicio" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Verificar novamente" })).toBeEnabled();
});

test("all navigation, provider, receipt, and account controls work", async ({ page }) => {
  await page.goto("/?state=active");
  await expect(page.getByRole("heading", { name: "Hoje você economizou." })).toBeVisible();
  const brandMark = page.locator(".brand-mark").first();
  await expect(brandMark).toBeVisible();
  await expect.poll(() => brandMark.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth >= 1024)).toBe(true);

  await page.getByRole("button", { name: "Ver relatório" }).click();
  await expect(page.getByRole("heading", { name: "Atividade" })).toBeVisible();
  await page.getByRole("button", { name: "atenção" }).click();
  await page.locator(".activity-provider-filter select").selectOption("all");
  const activityDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar recibos" }).click();
  await expect((await activityDownload).suggestedFilename()).toBe("simplicio-activity.json");

  await page.getByRole("button", { name: "Início" }).click();
  await page.getByRole("button", { name: "Abrir diagnóstico" }).click();
  await expect(page.getByRole("heading", { name: "Configurações" })).toBeVisible();
  const diagnosticDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar diagnóstico" }).click();
  await expect((await diagnosticDownload).suggestedFilename()).toBe("simplicio-diagnostic.json");

  await page.getByRole("button", { name: "Providers" }).click();
  await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
  await page.getByRole("button", { name: "Disponíveis" }).click();
  await page.getByRole("button", { name: "Todos" }).click();
  await page.getByRole("button", { name: "Ver detalhes" }).first().click();
  await expect(page.getByRole("button", { name: "Fechar detalhes" })).toBeVisible();
  await page.getByRole("button", { name: "Fechar detalhes" }).click();
  await page.getByRole("button", { name: /Entender os estados/ }).click();
  await expect(page.getByText("handshake atual e registro válido")).toBeVisible();
  await page.getByRole("button", { name: /Ocultar estados/ }).click();

  await page.getByRole("button", { name: "Memória" }).click();
  await expect(page.getByRole("heading", { name: "Memória" })).toBeVisible();
  await page.getByRole("button", { name: "Atividade" }).click();
  await expect(page.getByRole("heading", { name: "Atividade" })).toBeVisible();
  await page.getByRole("button", { name: "Abrir configurações da conta" }).click();
  await expect(page.getByRole("heading", { name: "Configurações" })).toBeVisible();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(page.getByRole("heading", { name: "Entre no Simplicio" })).toBeVisible();
});

test("Bot Center exposes the canonical roster, timeline, rooms, and honest computer state", async ({ page }) => {
  await page.goto("/?state=active&view=bot");
  await expect(page.getByRole("heading", { name: "Bot Center" })).toBeVisible();
  await expect(page.getByText("Roster canônico")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cora" })).toBeVisible();
  await expect(page.getByText("Rooms", { exact: true })).toBeVisible();
  await expect(page.getByText("computer_backend_unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Assumir controle" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Aprovar" })).toBeVisible();
});

test("primary layouts fit desktop and compact widths", async ({ page }) => {
  for (const width of [1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const view of ["home", "providers", "activity", "memory", "settings"]) {
      await page.goto(`/?state=active&view=${view}`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      expect(overflow, `${view} overflows at ${width}px`).toBe(false);
    }
  }
});
