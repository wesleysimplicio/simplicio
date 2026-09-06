import { expect, test } from "@playwright/test";

test("the two-step entry keeps keyboard focus on its next supported action", async ({ page }, testInfo) => {
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 740 });
    await page.goto("/?state=signed_out");
    const start = page.getByRole("button", { name: "Começar", exact: true });
    await expect(start).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath(`welcome-${width}.png`) });
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toBeFocused();
    await expect(page.getByRole("textbox")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`login-${width}.png`) });
    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toBeFocused();
  }
});
