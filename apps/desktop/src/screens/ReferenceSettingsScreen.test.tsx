import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createDemoSnapshot } from "../demo";
import { REFERENCE_SCREENS, type ReferenceSettingsView } from "../reference_screens";
import type { DesktopSnapshot } from "../contracts";
import { ReferenceSettingsScreen, createReferenceSettingsEvidence, copyReferenceCommand, REFERENCE_QUICK_COMMANDS } from "./ReferenceSettingsScreen";

function snapshot(runtime = false): DesktopSnapshot {
  const value = structuredClone(createDemoSnapshot("active"));
  if (runtime) {
    value.source = "runtime";
    if (value.botCenter) value.botCenter.source = "runtime";
  }
  return value;
}

function markup(view: ReferenceSettingsView, value = snapshot()) {
  return renderToStaticMarkup(<ReferenceSettingsScreen view={view} snapshot={value} onNavigate={() => {}} onRefresh={() => {}} />);
}

afterEach(() => { vi.useRealTimers(); });

describe("reference settings route coverage", () => {
  it.each(REFERENCE_SCREENS)("renders the distinct $id surface with its exact navigation heading", (screen) => {
    const html = markup(screen.id);
    expect(html).toContain("<h1>" + screen.label + "</h1>");
    expect(html).toContain('data-settings-view="' + screen.id + '"');
    expect(html).toContain("<h2>");
    expect(html).toContain("Prévia visual.");
    expect(html).toContain('aria-label="Atualizar consulta do Runtime"');
    expect(html).toContain("Nenhum estado da prévia é usado como comprovação");
    expect(html).not.toContain("voce@example.com");
    expect(html).not.toContain("window.open");
    expect(html).not.toMatch(/<input[^>]+type="(?:password|email|url)"/);
    expect(html).not.toContain("<form");
  });

  it.each(REFERENCE_SCREENS)("renders $id from a real-shaped snapshot without acquiring more privileges", (screen) => {
    const html = markup(screen.id, snapshot(true));
    expect(html).toContain("<h1>" + screen.label + "</h1>");
    expect(html).not.toContain("Prévia visual.");
    expect(html).toContain("Abrir esta tela não renova a consulta nem autoriza ações.");
    expect(html).not.toContain("voce@example.com");
    expect(html).not.toContain("storage.setItem");
  });

  it("keeps copy actions clearly distinct from execution", () => {
    const html = markup("quick-commands");
    for (const command of Object.values(REFERENCE_QUICK_COMMANDS)) {
      expect(html).toContain(command.command);
      expect(html).toContain('aria-label="Copiar ' + command.label + '"');
    }
    expect(html).toContain("Copiar não executa");
    expect(html).not.toContain("Copiado");
  });

  it("does not infer an admitted parallel capacity from the displayed bot inventory", () => {
    const html = markup("orchestration", snapshot(true));
    expect(html).toContain("O limite de paralelismo não foi consultado nesta tela.");
    expect(html).toContain("Limite não consultado");
    expect(html).not.toContain("até 32 bots");
  });

  it("does not render fake pairing codes, QR images, cookies or addresses", () => {
    const html = markup("mobile", snapshot(true));
    expect(html).toContain("Nenhum código emitido");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Gerar QR code<\/button>/);
    expect(html).not.toMatch(/<img|<canvas|(?:orca|simplicio):\/\/pair|192\.168|ws:\/\//);
    expect(markup("browser")).not.toContain('type="password"');
  });

  it("does not infer OS permissions from healthy Runtime or computer session availability", () => {
    const value = snapshot(true);
    if (value.botCenter) value.botCenter.computer.available = true;
    const html = markup("permissions", value);
    expect(html).toContain("Não consultada");
    expect(html).not.toMatch(/>Concedida<|>Negada<|GRANTED|DENIED/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Solicitar microfone<\/button>/);
    expect(markup("computer-use", value)).toContain("Permissões do sistema são verificadas separadamente.");
  });

  it("does not treat the public plugin catalog as an installed inventory", () => {
    const html = markup("plugins", snapshot(true));
    expect(html).toContain("Catálogo público");
    expect(html).toContain("Instalação não verificada");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Instalar Simplicio<\/button>/);
    expect(html).not.toMatch(/>Instalado<|>Instalados<|>Ativar plugin</);
    expect(html).toContain("Ele não comprova a instalação");
  });

  it("does not reuse the Simplicio login as provider-account authentication", () => {
    const value = snapshot(true);
    const provider = value.providers[0];
    provider.installState = "installed";
    provider.registrationState = "registered";
    provider.handshakeState = "live";
    provider.freshness = "current";
    const html = markup("provider-accounts", value);
    expect(html).toContain("Handshake MCP confirmado");
    expect(html).toContain("Identidade e sessão não consultadas");
    expect(html).not.toMatch(/>Conta ativa<|>Autenticado<|>System default</);
  });

  it.each([false, true])("does not expose hidden agent navigation from visible accounts (runtime=%s)", (runtime) => {
    const html = markup("provider-accounts", snapshot(runtime));
    expect(html).not.toContain("Ver agente e IDE");
    expect(html).toContain("Abrir conta Simplicio");
  });

  it("disables refresh while another root action owns its lock", () => {
    const html = renderToStaticMarkup(<ReferenceSettingsScreen view="voice" snapshot={snapshot()} onNavigate={() => {}} onRefresh={() => {}} busy />);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Atualizar consulta do Runtime"/);
    expect(html).toContain("Consultando…");
  });
});

describe("bounded read-only settings evidence", () => {
  it("discards positive demo data from every runtime evidence lane", () => {
    const evidence = createReferenceSettingsEvidence(snapshot());
    expect(evidence.providers).toEqual([]);
    expect(evidence.bots).toEqual([]);
    expect(evidence.skills).toEqual([]);
    expect(evidence.models).toEqual([]);
    expect(evidence.computer).toBeNull();
    expect(evidence.artifacts).toEqual([]);
    expect(evidence.runtimeVersion).toBe("Não verificada na prévia");
  });

  it("does not promote a label to a live connection when handshake is missing", () => {
    const value = snapshot(true);
    value.providers[0] = { ...value.providers[0], state: "connected", installState: "installed", registrationState: "registered", handshakeState: "unverified", freshness: "current" };
    expect(createReferenceSettingsEvidence(value).providers.find((provider) => provider.id === value.providers[0].id)?.state).toBe("registered");
  });

  it("does not use preview Agent Plane evidence inside a Runtime snapshot", () => {
    const value = snapshot(true);
    if (value.botCenter) value.botCenter.source = "preview";
    const evidence = createReferenceSettingsEvidence(value);
    expect(evidence.bots).toEqual([]);
    expect(evidence.models).toEqual([]);
    expect(evidence.computer).toBeNull();
    expect(evidence.artifacts).toEqual([]);
  });

  it("keeps identity, prompts, configuration, local paths and secret-like labels out", () => {
    const value = snapshot(true);
    value.access.email = "private-person@example.test";
    value.access.displayName = "Private Name";
    value.providers[0].detail = "private-config-body";
    value.providers[0].name = "/Users/private-person/secrets";
    const center = value.botCenter!;
    center.bots[0].displayName = "pypi-abcdefghijklmnopqrstuvwxyz";
    center.bots[0].toolset = ["/Users/private/tools", "tool-a"];
    center.bots[0].skills = ["C:\\Users\\private\\skill", "skill-a"];
    center.sessions[0].events[0].content = "private-prompt-body";
    const serialized = JSON.stringify(createReferenceSettingsEvidence(value));
    expect(serialized).not.toMatch(/private-person|Private Name|private-config-body|private-prompt-body|pypi-abcdefghijklmnopqrstuvwxyz|C:\\\\Users/);
    expect(serialized).toContain("tool-a");
    expect(serialized).toContain("skill-a");
  });

  it("bounds provider, bot, model, skill and tool collections", () => {
    const value = snapshot(true);
    const provider = value.providers[0];
    value.providers = Array.from({ length: 50 }, (_, index) => ({ ...provider, id: "provider-" + index }));
    const center = value.botCenter!;
    const bot = center.bots[0];
    center.bots = Array.from({ length: 50 }, (_, index) => ({ ...bot, botId: "bot-" + index, model: "model-" + index, skills: Array.from({ length: 150 }, (_, skill) => "skill-" + skill), toolset: Array.from({ length: 150 }, (_, tool) => "tool-" + tool) }));
    const evidence = createReferenceSettingsEvidence(value);
    expect(evidence.providers).toHaveLength(32);
    expect(evidence.bots).toHaveLength(32);
    expect(evidence.models).toHaveLength(32);
    expect(evidence.skills).toHaveLength(128);
    expect(evidence.tools).toHaveLength(128);
  });

  it("renders metadata as inert text and degrades invalid timestamps", () => {
    const value = snapshot(true);
    value.generatedAt = "not-a-date";
    const center = value.botCenter!;
    center.bots[0].displayName = '<img src="https://example.test/private" onerror="alert(1)">';
    const html = markup("orchestration", value);
    expect(html).not.toContain('<img src="https://example.test');
    expect(html).toContain("&lt;img");
    expect(html).toContain("Data não informada");
    expect(html).not.toContain("Invalid Date");
  });
});

describe("fixed command clipboard operation", () => {
  it("copies only the selected allowlisted text", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    expect(await copyReferenceCommand("version", write)).toBe("copied");
    expect(write).toHaveBeenCalledExactlyOnceWith("simplicio version");
  });

  it("rejects unknown keys and missing APIs without trying a fallback executor", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    expect(await copyReferenceCommand(JSON.parse('"__proto__"'), write)).toBe("unavailable");
    expect(await copyReferenceCommand("version", undefined)).toBe("unavailable");
    expect(write).not.toHaveBeenCalled();
  });

  it("handles explicit denial and synchronous errors", async () => {
    expect(await copyReferenceCommand("version", async () => { throw new Error("denied"); })).toBe("unavailable");
    expect(await copyReferenceCommand("version", () => { throw new Error("not allowed"); })).toBe("unavailable");
  });

  it("settles uncertainty after four seconds, never retries, and ignores late success", async () => {
    vi.useFakeTimers();
    let resolve!: () => void;
    const write = vi.fn(() => new Promise<void>((done) => { resolve = done; }));
    const result = copyReferenceCommand("version", write);
    await vi.advanceTimersByTimeAsync(4000);
    expect(await result).toBe("uncertain");
    expect(write).toHaveBeenCalledTimes(1);
    resolve();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(await result).toBe("uncertain");
    expect(write).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels the UI wait without claiming to cancel an already pending clipboard request", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    let reject!: (reason: Error) => void;
    const write = vi.fn(() => new Promise<void>((_resolve, fail) => { reject = fail; }));
    const result = copyReferenceCommand("access", write, controller.signal);
    await vi.advanceTimersByTimeAsync(1);
    controller.abort();
    expect(await result).toBe("cancelled");
    reject(new Error("late denial"));
    await vi.advanceTimersByTimeAsync(10_000);
    expect(write).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not start a clipboard request for an already cancelled view", async () => {
    const controller = new AbortController();
    controller.abort();
    const write = vi.fn().mockResolvedValue(undefined);
    expect(await copyReferenceCommand("plan", write, controller.signal)).toBe("cancelled");
    expect(write).not.toHaveBeenCalled();
  });
});
