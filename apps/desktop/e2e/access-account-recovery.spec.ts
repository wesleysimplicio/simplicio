import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type LockedState = "inactive" | "unknown";
type RecoveryTestWindow = Window & {
  __accessRecoveryCalls: string[];
  __accessFinishLogout?: () => void;
  __accessFinishLogin?: () => void;
};

async function mockAccountRecovery(page: Page, state: LockedState, options: {
  failLogout?: boolean;
  failSnapshot?: boolean;
  anonymous?: boolean;
  failLogin?: boolean;
  loginRemainsUnknown?: boolean;
  logoutRemainsUnknown?: boolean;
} = {}) {
  const snapshot = createDemoSnapshot(state);
  snapshot.source = "runtime";
  if (options.anonymous) snapshot.access = { ...snapshot.access, identityKnown: false, entitlementKnown: false, displayName: null, email: null, plan: null };
  const signedOut = createDemoSnapshot("signed_out");
  signedOut.source = "runtime";
  const active = createDemoSnapshot("active");
  active.source = "runtime";
  await page.addInitScript(({ snapshot, signedOut, active, options }) => {
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
            return options.logoutRemainsUnknown ? snapshot : signedOut;
          }
          if (command === "desktop_login") {
            await new Promise<void>((resolve) => Object.assign(window, { __accessFinishLogin: resolve }));
            if (options.failLogin) throw "runtime_oauth_timeout";
            return options.loginRemainsUnknown ? snapshot : active;
          }
          if (command === "refresh_desktop_snapshot") return snapshot;
          // Native menu subscriptions have no account or installation effects.
          if (command === "plugin:event|listen") return 1;
          if (command === "plugin:event|unlisten") return;
          throw `Unexpected account recovery IPC: ${command}`;
        },
      },
    });
  }, { snapshot, signedOut, active, options });
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

    await expect(page.getByRole("alert")).toContainText("A saída da conta não foi confirmada.");
    await expect(page.getByRole("alert")).not.toContainText("logout_unconfirmed");
    await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ative o Simplicio", exact: true })).toHaveCount(0);
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

for (const failSnapshot of [false, true]) {
  test(`${failSnapshot ? "failed snapshot" : "unknown access without identity"} can explicitly log in and reach active setup (mocked IPC)`, async ({ page }) => {
    await mockAccountRecovery(page, "unknown", { anonymous: true, failSnapshot });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ative o Simplicio", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
    await expectNoImplicitEffects(page);

    await page.getByRole("button", { name: "Entrar ou reconectar", exact: true }).dblclick();
    const pending = page.getByRole("button", { name: "Aguardando navegador…", exact: true });
    await expect(pending).toBeDisabled();
    await expect(pending).toHaveAttribute("aria-busy", "true");
    await expect(page.getByRole("status")).toContainText("O acesso permanece desconhecido");
    await expect(page.getByRole("button", { name: "Aguarde…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Sair da conta", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "Abrir diagnóstico", exact: true }).click();
    await expect(page.getByText("Estado de acesso desconhecido", { exact: true })).toBeVisible();
    const pendingCalls = await page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls);
    expect(pendingCalls.filter((command) => command === "desktop_login")).toHaveLength(1);
    expect(pendingCalls).not.toContain("refresh_desktop_snapshot");
    expect(pendingCalls).not.toContain("desktop_logout");

    await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogin?.());
    await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeEnabled();
    await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    const calls = await page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls);
    expect(calls.filter((command) => command === "desktop_login")).toHaveLength(1);
    for (const command of ["desktop_logout", "desktop_open_subscription", "desktop_plan_integrations", "desktop_repair_providers"]) {
      expect(calls).not.toContain(command);
    }
  });
}

for (const failLogin of [false, true]) {
  test(`${failLogin ? "failed" : "unverified"} login keeps unknown access gated without assuming active or inactive (mocked IPC)`, async ({ page }) => {
    await mockAccountRecovery(page, "unknown", { anonymous: true, failLogin, loginRemainsUnknown: true });
    await page.goto("/");
    await page.getByRole("button", { name: "Entrar ou reconectar", exact: true }).click();
    await expect(page.getByRole("button", { name: "Aguardando navegador…", exact: true })).toBeDisabled();
    await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogin?.());
    await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeEnabled();
    await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Ative o Simplicio", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
    if (failLogin) {
      await expect(page.getByRole("alert")).toContainText("O resultado final do login não foi confirmado");
      await expect(page.getByRole("alert")).not.toContainText("runtime_oauth_timeout");
    }
    await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
    await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeEnabled();
    const calls = await page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls);
    expect(calls.filter((command) => command === "desktop_login")).toHaveLength(1);
    expect(calls.filter((command) => command === "refresh_desktop_snapshot")).toHaveLength(1);
    expect(calls).not.toContain("desktop_logout");
    expect(calls).not.toContain("desktop_repair_providers");
  });
}

test("legacy logout returning unknown still permits a later explicit login (mocked IPC)", async ({ page }) => {
  await mockAccountRecovery(page, "unknown", { anonymous: true, logoutRemainsUnknown: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeDisabled();
  await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogout?.());
  await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeEnabled();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await expectNoImplicitEffects(page);
  await page.getByRole("button", { name: "Entrar ou reconectar", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Aguardando navegador…", exact: true })).toBeDisabled();
  await page.evaluate(() => (window as RecoveryTestWindow).__accessFinishLogin?.());
  await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toBeVisible();
  const calls = await page.evaluate(() => (window as RecoveryTestWindow).__accessRecoveryCalls);
  expect(calls.filter((command) => command === "desktop_logout")).toHaveLength(1);
  expect(calls.filter((command) => command === "desktop_login")).toHaveLength(1);
  expect(calls.indexOf("desktop_logout")).toBeLessThan(calls.indexOf("desktop_login"));
  expect(calls).not.toContain("desktop_repair_providers");
});
