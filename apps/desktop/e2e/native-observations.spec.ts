import { test, expect } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
test("reads native permissions and quotas and opens only the requested settings pane", async ({ page }) => {
  const snapshot = createDemoSnapshot("active"); snapshot.source = "runtime";
  await page.addInitScript(({ snapshot }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    let accessibilityGranted = false;
    Object.assign(window, { __grantAccessibility: () => { accessibilityGranted = true; } });
    Object.assign(window, { __permissionCalls: calls, __TAURI_INTERNALS__: { invoke: async (command: string, args: Record<string, unknown> = {}) => {
      calls.push({ command, args });
      if (command === "desktop_snapshot") return snapshot;
      if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
      if (command === "desktop_preparation_status") return true;
      if (command === "desktop_permissions") return { schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows: ["microphone","camera","screen","accessibility","files","automation","network","devices"].map(id => ({id,status: id === "microphone" ? "granted" : id === "camera" ? "not_determined" : id === "accessibility" && accessibilityGranted ? "granted" : "unknown",canOpenSettings:true})) };
      if (command === "desktop_open_permission_settings") return;
      if (command === "desktop_request_media_permission") return { schema: "simplicio.desktop-permissions/v1", source: "operating_system", rows: ["microphone","camera","screen","accessibility","files","automation","network","devices"].map(id => ({id,status: id === "camera" ? "denied" : "unknown",canOpenSettings:true})) };
      if (command === "desktop_provider_quotas") return {schema:"simplicio.provider-quotas/v2",status:"available",observedAt:1900000000,providers:[{id:"codex",source:"codex_app_server",accountScope:"local_authenticated_account",observedAt:1900000000,redacted:true,status:"fresh",windows:[{usedPercent:21,windowDurationMins:10080,resetsAt:1900000000}]},{id:"grok",source:"grok_cli_billing",accountScope:"local_cli_session",observedAt:1900000000,redacted:true,status:"fresh",windows:[{usedPercent:37,windowDurationMins:10080,resetsAt:1900000000}]}]};
      if (command === "plugin:event|listen") return 1;
      throw "fixture_unavailable";
    } } });
  }, { snapshot });
  await page.goto("/?view=permissions");
  await expect(page.getByText("Concedida", { exact: true })).toBeVisible();
  await page.getByRole("button", {name:"Revisar microfone",exact:true}).click();
  await expect(page.getByRole("status").filter({hasText:"Ajustes do Sistema abertos"})).toBeVisible();
  await page.getByRole("button", {name:"Solicitar câmera",exact:true}).click();
  await expect(page.getByText("Negada", {exact:true})).toBeVisible();
  const calls = await page.evaluate(() => (window as unknown as {__permissionCalls: Array<{command:string;args:Record<string,unknown>}>}).__permissionCalls);
  expect(calls.filter(c=>c.command==="desktop_open_permission_settings")).toEqual([{command:"desktop_open_permission_settings",args:{permission:"microphone"}}]);
  await page.getByRole("button", {name:"Codex 21% usado",exact:true}).click();
  await expect(page.getByRole("region",{name:"Cotas dos agentes"})).toContainText("Semanal · 21% usado");
  const panel = page.getByRole("region", {name:"Cotas dos agentes"});
  await expect(panel.getByText("Renova em", {exact:false})).toHaveCount(2);
  await panel.getByRole("button", {name:"Compacto", exact:true}).click();
  await expect(panel.getByRole("button", {name:"Compacto", exact:true})).toHaveAttribute("aria-pressed", "true");
  await expect(panel.getByText("Renova em", {exact:false})).toHaveCount(0);
  await expect(panel.getByRole("progressbar", {name:"Uso da janela de 10080 minutos"}).first()).toHaveAttribute("value", "21");
  await panel.getByRole("button", {name:"Detalhado", exact:true}).click();
  await expect(panel.getByText("Renova em", {exact:false})).toHaveCount(2);
  await expect(panel.getByRole("progressbar", {name:"Uso da janela de 10080 minutos"}).nth(1)).toHaveAttribute("value", "37");
  await page.getByRole("button",{name:"Fechar cotas"}).click();
  await expect(page.getByRole("region",{name:"Cotas dos agentes"})).toHaveCount(0);
  await page.evaluate(() => (window as unknown as {__grantAccessibility:()=>void}).__grantAccessibility());
  // No focus event and no refresh click: external OS change must be re-read.
  await expect(page.locator(".ref-permission-list").getByText("Concedida", {exact:true})).toHaveCount(2);
  // Computer Use currently has a direct route but is excluded from the navigation policy.
  await page.goto("/?view=computer-use");
  await page.evaluate(() => (window as unknown as {__grantAccessibility:()=>void}).__grantAccessibility());
  await expect(page.getByText("Estado consultado diretamente no macOS para este aplicativo.", {exact:true})).toBeVisible();
  await expect(page.getByText("Concedida", {exact:true})).toHaveCount(1);
  await expect(page.getByText("O Desktop ainda não consulta essa permissão.", {exact:false})).toHaveCount(0);
  await page.goto("/?view=provider-accounts");
  await page.getByRole("button", {name:"Consultar conexão Codex", exact:true}).click();
  await page.getByRole("button", {name:"Consultar conexão Grok", exact:true}).click();
  await expect(page.getByText("Consulta de cota confirmada. A identidade da conta não foi consultada.", {exact:true})).toHaveCount(2);
  await expect(page.getByRole("button", {name:"Adicionar conta Grok", exact:true})).toBeDisabled();
});
