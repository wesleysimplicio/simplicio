import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type ReferenceFolderWindow = Window & {
  __referenceFolderCalls: string[];
  __finishReferenceFolder?: (path: string | null) => void;
};

test("choosing a native folder fills a reviewable path without adding a project implicitly (mocked IPC)", async ({ page }, testInfo) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  const project = { id: "project-" + "d".repeat(64), name: "didaticos", path: "/tmp/didaticos" };
  await page.addInitScript(({ snapshot, project }) => {
    Object.assign(window, { __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "plugin:dialog|open") return project.path;
        if (command === "desktop_validate_project") return project;
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_project_command";
      },
    } });
  }, { snapshot, project });
  await page.goto("/?view=home");
  await page.getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Adicionar projeto", exact: true });
  const choose = dialog.getByRole("button", { name: "Escolher pasta…", exact: true });
  await expect(choose).toBeFocused();
  await choose.click();
  await expect(page.getByLabel("Caminho da pasta")).toHaveValue("/tmp/didaticos");
  await expect(page.getByLabel("Caminho da pasta")).toBeFocused();
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("button", { name: "Abrir projeto didaticos", exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("folder-review.png") });
  await dialog.getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "didaticos", exact: true })).toBeVisible();
});

test("canceling the system picker preserves the typed path and restores focus without validation (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot }) => {
    const calls: string[] = [];
    Object.assign(window, { __referenceFolderCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        calls.push(command);
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "plugin:dialog|open") return new Promise<string | null>((resolve) => {
          (window as ReferenceFolderWindow).__finishReferenceFolder = resolve;
        });
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_folder_command";
      },
    } });
  }, { snapshot });
  await page.goto("/?view=home");
  const add = page.getByRole("button", { name: "Adicionar projeto", exact: true });
  await add.click();
  const dialog = page.getByRole("dialog", { name: "Adicionar projeto", exact: true });
  await page.getByLabel("Caminho da pasta").fill("/tmp/rascunho");
  await dialog.getByRole("button", { name: "Escolher pasta…", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Escolhendo pasta…", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Cancelar", exact: true })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  await page.evaluate(() => (window as ReferenceFolderWindow).__finishReferenceFolder?.(null));
  await expect(dialog.getByRole("button", { name: "Escolher pasta…", exact: true })).toBeFocused();
  await expect(page.getByLabel("Caminho da pasta")).toHaveValue("/tmp/rascunho");
  await expect(page.getByRole("alert")).toHaveCount(0);
  const calls = await page.evaluate(() => (window as ReferenceFolderWindow).__referenceFolderCalls);
  expect(calls.filter((call) => call === "plugin:dialog|open")).toHaveLength(1);
  expect(calls).not.toContain("desktop_validate_project");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(add).toBeFocused();
});

test("manual path errors stay actionable and are cleared when the path changes", async ({ page }) => {
  await page.goto("/");
  const add = page.getByRole("button", { name: "Adicionar projeto", exact: true });
  await add.click();
  const path = page.getByLabel("Caminho da pasta");
  await path.fill("/tmp/didaticos");
  await page.getByRole("dialog").getByRole("button", { name: "Adicionar projeto", exact: true }).click();
  await expect(path).toHaveAttribute("aria-invalid", "true");
  await expect(path).toHaveAttribute("aria-describedby", /project-path-error/);
  await expect(path).toBeFocused();
  await expect(page.getByRole("alert")).toContainText("demonstração no navegador não acessa seus arquivos");
  await path.fill("/tmp/outro-projeto");
  await expect(path).toHaveAttribute("aria-invalid", "false");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(add).toBeFocused();
});
