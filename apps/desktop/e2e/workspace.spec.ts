import { expect, test } from "@playwright/test";

test("workspace conformance keeps the five primary surfaces discoverable", async ({ page }) => {
  await page.goto("/?state=active&view=today");
  for (const [label, heading] of [["Today", "Today"], ["Chats", "Chats"], ["Teams", "Teams"], ["Automations", "Automations"], ["Apps", "Apps"]] as const) {
    await page.getByRole("button", { name: label }).click();
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Novo", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Buscar/ })).toBeDisabled();
});

test("workspace conformance exposes unavailable capabilities honestly", async ({ page }) => {
  await page.goto("/?state=active&view=apps");
  await expect(page.getByText("capability.registry_unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Abrir", exact: true }).first()).toBeDisabled();
  await page.getByRole("button", { name: "Chats" }).click();
  await expect(page.getByText("agent_api_unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar" })).toBeDisabled();
});
