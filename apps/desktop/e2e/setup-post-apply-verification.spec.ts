import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type VerificationState = "clean" | "pending" | "absent" | "missing" | "duplicate" | "wrong-source" | "plan-error" | "stable-pending" | "stable-absent" | "stable-missing";
type SetupTestWindow = Window & { __setupVerificationCalls: string[]; __finishSetupVerification?: () => void };

async function mockSetupVerification(page: Page, options: { state?: VerificationState; pauseVerification?: boolean; duplicateReview?: boolean; unchangedReview?: boolean; emptyReview?: boolean } = {}) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  snapshot.providers.forEach((provider) => { provider.handshakeState = "unverified"; });
  await page.addInitScript(({ snapshot, options }) => {
    let applied = false;
    const calls: string[] = [];
    const mixedTargets = [{ label: "codex", changed: true, exists: false }, { label: "hermes", changed: true, exists: true }, { label: "stable", changed: false, exists: true }];
    const reviewedChanges = options.emptyReview ? [] : options.unchangedReview ? mixedTargets.filter((row) => !row.changed) : mixedTargets;
    Object.assign(window, { __setupVerificationCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push(command);
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") {
          if (!applied) return {
            schema: "simplicio.desktop-integration-plan/v1", source: "runtime", planDigest: `sha256:${"a".repeat(64)}`,
            changes: options.duplicateReview ? [...reviewedChanges, reviewedChanges[0]] : reviewedChanges,
          };
          if (options.pauseVerification) await new Promise<void>((resolve) => Object.assign(window, { __finishSetupVerification: resolve }));
          if (options.state === "plan-error") throw "post_apply_plan_unavailable";
          let changes = reviewedChanges.map((row) => ({ ...row, exists: true, changed: false }));
          if (options.state === "pending") changes[0].changed = true;
          if (options.state === "absent") changes[0].exists = false;
          if (options.state === "missing") changes = changes.filter((row) => row.label !== "codex");
          if (options.state === "duplicate") changes.push({ label: "codex", changed: false, exists: true });
          if (options.state === "stable-pending") changes = changes.map((row) => row.label === "stable" ? { ...row, changed: true } : row);
          if (options.state === "stable-absent") changes = changes.map((row) => row.label === "stable" ? { ...row, exists: false } : row);
          if (options.state === "stable-missing") changes = changes.filter((row) => row.label !== "stable");
          // Discovery of another client is not permission to install it during verification.
          changes.push({ label: "new-client", changed: true, exists: false });
          return { schema: "simplicio.desktop-integration-plan/v1", source: options.state === "wrong-source" ? "preview" : "runtime",
            planDigest: `sha256:${"b".repeat(64)}`, changes };
        }
        if (command === "desktop_repair_providers") {
          if (args.planDigest !== `sha256:${"a".repeat(64)}`) throw "integration_plan_changed_review_again";
          applied = true;
          return snapshot;
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw `Unexpected setup verification IPC: ${command}`;
      },
    } });
  }, { snapshot, options });
}

async function commandCount(page: Page, command: string) {
  return page.evaluate((command) => (window as SetupTestWindow).__setupVerificationCalls.filter((call) => call === command).length, command);
}

async function reviewAndApply(page: Page) {
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tudo pronto para revisar." })).toBeVisible();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
}

test("a confirmed apply remains at step 4 until the reviewed targets are rechecked, without requiring handshakes (mocked IPC)", async ({ page }) => {
  await mockSetupVerification(page, { pauseVerification: true });
  await reviewAndApply(page);
  await expect(page.getByRole("heading", { name: "Verificando o resultado…", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "3");
  await expect(page.getByRole("button", { name: "Voltar ao app", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Mostrar detalhes", exact: true }).click();
  const details = page.getByRole("region", { name: "Detalhes da configuração", exact: true });
  await expect(details).toContainText("Aplicação confirmada pelo Runtime.");
  await expect(details).toContainText("Conferência dos destinos: ainda não confirmada.");
  await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toHaveCount(0);
  expect(await commandCount(page, "desktop_plan_integrations")).toBe(2);

  await page.evaluate(() => (window as SetupTestWindow).__finishSetupVerification?.());
  await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "4");
  await expect(details).toContainText("Conferência dos destinos: confirmada por nova leitura do plano.");
  await expect(details).toContainText(`sha256:${"b".repeat(64)}`);
  await expect(page.getByText(/Registro não significa conexão ativa/)).toBeVisible();
  expect(await commandCount(page, "desktop_repair_providers")).toBe(1);
  expect(await commandCount(page, "refresh_desktop_snapshot")).toBe(2);
});

for (const state of ["pending", "absent", "missing", "duplicate", "wrong-source", "plan-error", "stable-pending", "stable-absent", "stable-missing"] as const) {
  test(`post-apply ${state} evidence cannot claim configuration success or retry installation (mocked IPC)`, async ({ page }) => {
    await mockSetupVerification(page, { state });
    await reviewAndApply(page);
    await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
    await expect(page.getByRole("progressbar")).toHaveAttribute("value", "3");
    await expect(page.getByRole("alert")).toContainText("O plano foi aplicado, mas a verificação final falhou.");
    await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Mostrar detalhes", exact: true }).click();
    await expect(page.getByRole("region", { name: "Detalhes da configuração", exact: true })).toContainText("Conferência dos destinos: ainda não confirmada.");
    expect(await commandCount(page, "desktop_repair_providers")).toBe(1);
    expect(await commandCount(page, "desktop_plan_integrations")).toBe(2);
    await expect(page.getByRole("button", { name: "Revisar novamente", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Atualizar diagnóstico", exact: true })).toBeEnabled();
  });
}

for (const state of ["stable-pending", "stable-missing"] as const) {
  test(`an unchanged-only reviewed plan fails on ${state} drift (mocked IPC)`, async ({ page }) => {
    await mockSetupVerification(page, { state, unchangedReview: true });
    await reviewAndApply(page);
    await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
    await expect(page.getByRole("progressbar")).toHaveAttribute("value", "3");
    await expect(page.getByRole("alert")).toContainText("O plano foi aplicado, mas a verificação final falhou.");
    await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toHaveCount(0);
    expect(await commandCount(page, "desktop_repair_providers")).toBe(1);
    expect(await commandCount(page, "desktop_plan_integrations")).toBe(2);
  });
}

test("a genuinely empty reviewed plan stays valid without applying newly discovered clients (mocked IPC)", async ({ page }) => {
  await mockSetupVerification(page, { emptyReview: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await expect(page.getByText("Nenhuma mudança foi proposta pelo Runtime.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toBeDisabled();
  expect(await commandCount(page, "desktop_repair_providers")).toBe(0);
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Configuração concluída.", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "4");
  expect(await commandCount(page, "desktop_repair_providers")).toBe(1);
  expect(await commandCount(page, "desktop_plan_integrations")).toBe(2);
});

test("ambiguous reviewed target labels fail before consent or apply (mocked IPC)", async ({ page }) => {
  await mockSetupVerification(page, { duplicateReview: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("O Runtime não entregou um plano válido.");
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "1");
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toHaveCount(0);
  expect(await commandCount(page, "desktop_repair_providers")).toBe(0);
});

test("static browser preview cannot fabricate a clean post-apply plan", async ({ page }) => {
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Simular configuração", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("A demonstração não confirmou os destinos do plano revisado. Nenhum arquivo foi alterado.");
  await expect(page.getByRole("heading", { name: "Prévia concluída.", exact: true })).toHaveCount(0);
});
