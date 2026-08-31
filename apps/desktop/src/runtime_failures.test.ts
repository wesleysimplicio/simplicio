import { describe, expect, it } from "vitest";
import { runtimeFailureMessage } from "./runtime_failures";

describe("safe Runtime failure messages", () => {
  it("explains auth-only compatibility without claiming account state or reflecting output", () => {
    const unsupported = runtimeFailureMessage("runtime_auth_only_unsupported", "login");
    expect(unsupported).toContain("Atualize o Simplicio Desktop");
    expect(unsupported).toContain("Consulte o estado da conta");
    expect(runtimeFailureMessage("runtime_auth_result_unconfirmed", "login")).toContain("não confirmou um login sem configuração automática");
    expect(runtimeFailureMessage("runtime_auth_only_unsupported: SECRET", "login")).not.toContain("SECRET");
  });
  it("distinguishes the native query deadline from the Desktop waiting deadline", () => {
    expect(runtimeFailureMessage("runtime_query_timeout")).toContain("20 segundos");
    expect(runtimeFailureMessage(new Error("desktop_snapshot_timeout"))).toContain("ainda pode estar concluindo");
    expect(runtimeFailureMessage("runtime_query_timeout")).not.toContain("ainda pode estar concluindo");
  });

  it("does not turn OAuth timeout or a later command failure into an account conclusion", () => {
    expect(runtimeFailureMessage("runtime_oauth_timeout", "login")).toContain("3 minutos");
    expect(runtimeFailureMessage("runtime_not_started", "login")).toContain("Não foi possível iniciar um comando");
    for (const code of ["runtime_oauth_timeout", "runtime_query_timeout", "runtime_not_started", "runtime_stdout_limit", "unknown"]) {
      const message = runtimeFailureMessage(code, "login");
      expect(message).toContain("resultado final do login não foi confirmado");
      expect(message).toContain("Consulte o estado da conta antes de iniciar outro login");
      expect(message).not.toContain("login não foi iniciado");
      expect(message).not.toContain("assinatura inativa");
      expect(message).not.toContain("tentar novamente");
    }
    const message = runtimeFailureMessage("runtime_not_started", "logout");
    expect(message).toContain("saída da conta não foi confirmada");
    expect(message).not.toContain("logout não foi iniciado");
  });

  it("distinguishes bounded output failures and uncertain cleanup without exposing diagnostics", () => {
    expect(runtimeFailureMessage("runtime_stdout_limit")).toContain("resposta do Runtime ultrapassou o limite");
    expect(runtimeFailureMessage("runtime_stderr_limit")).toContain("saída de diagnóstico do Runtime ultrapassou o limite");
    expect(runtimeFailureMessage("runtime_output_unavailable")).toContain("Não foi possível obter a saída");
    expect(runtimeFailureMessage("runtime_process_cleanup_unconfirmed")).toContain("encerramento de um processo");
    expect(runtimeFailureMessage("runtime_process_cleanup_unconfirmed")).toContain("Novos comandos do Runtime estão bloqueados");
    expect(runtimeFailureMessage("runtime_install_timeout")).toContain("Não repita a instalação sem esclarecer o resultado");
    expect(runtimeFailureMessage("runtime_install_timeout")).toContain("5 minutos");
  });

  it("does not reflect unknown strings, object fields, oversized output or secrets", () => {
    for (const error of ["secret-do-not-reflect /private/path", new Error("secret-do-not-reflect"),
      "runtime_query_timeout: secret-do-not-reflect", "__proto__", "constructor", "x".repeat(100_000),
      { message: "runtime_not_started" }, null]) {
      const message = runtimeFailureMessage(error);
      expect(message).toContain("Não foi possível confirmar o resultado");
      expect(message).not.toContain("secret-do-not-reflect");
      expect(message).not.toContain("/private/path");
      expect(message.length).toBeLessThan(500);
    }
  });
});
