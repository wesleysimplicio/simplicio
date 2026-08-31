import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type LockedState = "inactive" | "unknown";
type RecoveryTestWindow = Window & {
  __accessRecoveryCalls: string[];
  __accessFinishLogout?: () => void;
};

async function mockAccountRecovery(page: Page, state: LockedState, options: { failLogout?: boolean; failSnapshot?: boolean } = {}) {
  const snapshot = createDemoSnapshot(state);
  snapshot.source = "runtime";
  const signedOut = createDemoSnapshot("signed_out");
  signedOut.source = "runtime";
  await page.addInitScript(({ snapshot, signedOut, options }) => {
    const calls: string[] = [];
    Object.assign(window, {
      __accessRecoveryCalls: calls,
      __TAURI_INTERNALS__: {
        invoke: async (command: string) => {
          calls.push(command);
          if (command === "desktop_snapshot") {
            if (options.failSnapshot) throw "snapshot_unavailable";
            return snapshot;
          }
          if (command === "desktop_logout") {
            await new Promise<void>((resolve) => Object.assign(window, { __accessFinishLogout: resolve }));
            if (options.failLogout) throw "logout_unconfirmed";
            return signedOut;
          }
          // Native menu subscriptions have no account or installation effects.
          if (command === "plugin:event|listen") return 1;
          if (command === "plugin:event|unlisten") return;
          throw `Unexpected account recovery IPC: ${command}`;
        },
      },
    });
  }, { snapshot, signedOut, options });
}

async function logoutCalls(page: Page) {
  return page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls.filter((command) => command === "desktop_logout"));
}

async function expectNoImplicitEffects(page: Page) {
  const calls = await page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls);
  expect(calls).not.toContain("desktop_login");
  expect(calls).not.toContain("desktop_open_subscription");
  expect(calls).not.toContain("desktop_plan_integrations");
  expect(calls).not.toContain("desktop_repair_providers");
}

for (const state of ["inactive", "unknown"] as const) {
  const heading = state === "inactive" ? "Ative o Simplicio" : "Tente novamente";

  test(`${state} access can sign out through Runtime without starting another login (mocked IPC)`, async ({ page }) => {
    await mockAccountRecovery(page, state);
    await page.goto("/?view=providers");
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Sair da conta", exact: true }).dblclick();

    const pendingLogout = page.getByRole("button", { name: "Saindo…", exact: true });
    await expect(pendingLogout).toBeDisabled();
    await expect(pendingLogout).toHaveAttribute("aria-busy", "true");
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
    expect(await logoutCalls(page)).toHaveLength(1);

    await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogout?.());
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Começar", exact: true }).click();
    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toBeVisible();
    await expectNoImplicitEffects(page);
  });

  test(`${state} logout failure stays gated and reports failure without a false signed-out state (mocked IPC)`, async ({ page }) => {
    await mockAccountRecovery(page, state, { failLogout: true });
    await page.goto("/?view=providers");
    await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
    await expect(page.getByRole("button", { name: "Saindo…", exact: true })).toBeDisabled();
    await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogout?.());

    await expect(page.getByRole("alert")).toContainText("Não foi possível sair com segurança.");
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sair da conta", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Continuar com Google", exact: true })).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
    expect(await logoutCalls(page)).toHaveLength(1);
    await expectNoImplicitEffects(page);
  });
}

test("a failed initial snapshot can recover through confirmed logout (mocked IPC)", async ({ page }) => {
  await mockAccountRecovery(page, "unknown", { failSnapshot: true });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Saindo…", exact: true })).toBeDisabled();
  await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogout?.());

  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toHaveCount(0);
  expect(await logoutCalls(page)).toHaveLength(1);
  await expectNoImplicitEffects(page);
});
