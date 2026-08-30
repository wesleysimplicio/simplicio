import { expect, test } from "@playwright/test";

test("white canvas, sidebar and panels survive system dark mode", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "dark" });
  for (const view of ["today", "chats", "teams", "automations", "apps", "providers", "tokens", "settings"]) {
    await page.goto(`/?state=active&view=${view}`);
    const surfaces = await page.evaluate(() => ["canvas", "sidebar", "surface", "surface-strong"].map((token) =>
      getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim()));
    expect(surfaces).toEqual(["#ffffff", "#ffffff", "#ffffff", "#ffffff"]);
    for (const selector of ["html", "body", ".app-shell", ".sidebar", ".topbar"]) {
      await expect(page.locator(selector)).toHaveCSS("background-color", "rgb(255, 255, 255)");
    }
    if (view === "tokens") await expect(page.locator(".token-query")).toHaveCSS("background-color", "rgb(255, 255, 255)");
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  }
  await page.goto("/?state=active&view=today");
  await page.screenshot({ path: testInfo.outputPath("desktop-white-today.png"), fullPage: true });
});

test("sign-in and access-gated pages use the same white background", async ({ page }, testInfo) => {
  for (const state of ["signed_out", "inactive", "unknown"]) {
    await page.goto(`/?state=${state}`);
    const selectors = state === "signed_out" ? [".access-layout", ".access-story", ".access-panel"] : [".locked-layout"];
    for (const selector of selectors) await expect(page.locator(selector)).toHaveCSS("background-color", "rgb(255, 255, 255)");
  }
  await page.goto("/?state=signed_out");
  await page.screenshot({ path: testInfo.outputPath("desktop-white-login.png"), fullPage: true });
});
