import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`login uses a borderless white surface and preserves keyboard focus at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 740 });
    await page.goto("/?state=signed_out");
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeFocused();
    await page.keyboard.press("Enter");

    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toBeVisible();
    for (const selector of [".entry-flow", ".entry-login", ".entry-login-card"]) {
      const surface = page.locator(selector);
      await expect(surface).toHaveCSS("border-top-width", "0px");
      await expect(surface).toHaveCSS("border-right-width", "0px");
      await expect(surface).toHaveCSS("border-bottom-width", "0px");
      await expect(surface).toHaveCSS("border-left-width", "0px");
      await expect(surface).toHaveCSS("box-shadow", "none");
    }
    await expect(page.locator(".entry-flow")).toHaveCSS("background-color", "rgb(255, 255, 255)");
    const mark = page.locator(".entry-mark");
    await expect(mark).toHaveAttribute("src", "/icon.png");
    await expect(mark).toHaveCSS("border-top-width", "0px");
    await expect(mark).toHaveCSS("border-right-width", "0px");
    await expect(mark).toHaveCSS("border-bottom-width", "0px");
    await expect(mark).toHaveCSS("border-left-width", "0px");
    await expect(mark).toHaveCSS("box-shadow", "none");
    await expect(mark).toHaveCSS("outline-style", "none");
    await expect(mark).toHaveCSS("object-fit", "cover");
    expect(await mark.evaluate((element) => {
      const image = element as HTMLImageElement;
      return image.naturalWidth > 0 && image.naturalHeight > 0 && image.complete;
    })).toBe(true);

    const google = page.getByRole("button", { name: "Continuar com Google", exact: true });
    await expect(google).toBeFocused();
    await expect(google).toBeEnabled();
    await expect(google).toHaveCSS("border-top-width", "1px");
    await expect(google).toHaveCSS("outline-style", "solid");
    await expect(google).toHaveCSS("outline-width", "2px");
    expect(await google.evaluate((element) => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);


    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`borderless-login-${width}.png`) });

  });
}
