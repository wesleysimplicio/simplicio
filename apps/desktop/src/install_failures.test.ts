import { describe, expect, it } from "vitest";
import { installFailureMessage, installFailureRecovery, parseInstallAttemptDiagnostic } from "./install_failures";

describe("safe installer failure messages", () => {
  it("shows only a bounded nonzero OS exit code and warns about partial effects", () => {
    for (const code of [1, 7, -1, -2_147_483_648, 2_147_483_647]) {
      const message = installFailureMessage(`integration_install_exit_code:${code}`);
      expect(message).toContain(`código ${code}.`);
      expect(message).toContain("alterações parciais");
    }
    for (const value of ["0", "2147483648", "-2147483649", "999999999999999", "1 extra"]) {
      expect(installFailureMessage(`integration_install_exit_code:${value}`)).not.toContain("encerrou com código");
    }
  });

  it("distinguishes invalid output, missing receipts and post-apply verification failure", () => {
    expect(installFailureMessage("integration_install_invalid_json")).toContain("resposta inválida");
    expect(installFailureMessage("integration_install_response_too_large")).toContain("limite permitido");
    expect(installFailureMessage("integration_install_receipt_unconfirmed")).toContain("recibo de instalação completo");
    expect(installFailureMessage(new Error("integration_install_applied_snapshot_unavailable"))).toContain("confirmou a aplicação");
    expect(installFailureMessage("integration_install_no_exit_code")).toContain("sem um código de saída confirmado");
  });

  it("never echoes native output, credentials, paths or object property names", () => {
    for (const error of ["secret-do-not-reflect /private/user/path", new Error("secret-do-not-reflect"),
      "__proto__", "constructor", { message: "secret-do-not-reflect" }, null, "x".repeat(100_000)]) {
      const message = installFailureMessage(error);
      expect(message).not.toContain("secret-do-not-reflect");
      expect(message).not.toContain("/private/user/path");
      expect(message).toContain("O Runtime não confirmou");
      expect(message.length).toBeLessThan(400);
    }
  });

  it("requires fresh review after a changed plan and does not claim a busy install failed", () => {
    expect(installFailureMessage("integration_plan_changed_review_again")).toContain("Revise a configuração");
    expect(installFailureMessage("integration_install_busy")).toContain("já está em andamento");
    expect(installFailureMessage("integration_install_busy")).not.toContain("alterações parciais");
  });

  it("permits a reviewed retry only when the installer is known not to have started", () => {
    const message = installFailureMessage("integration_install_not_started");
    expect(message).toContain("não foi iniciado");
    expect(message).toContain("Revise um novo plano");
    expect(message).toContain("antes de tentar novamente");
    expect(message).not.toContain("alterações parciais");
  });

  it("keeps post-start uncertainty blocked without treating refresh or restart as reconciliation", () => {
    for (const code of [
      "integration_install_timeout", "integration_install_stderr_too_large",
      "integration_install_cleanup_unconfirmed", "integration_install_reconciliation_required",
      "integration_install_output_unavailable", "integration_install_no_exit_code",
      "integration_install_invalid_json", "integration_install_response_too_large",
      "integration_install_receipt_unconfirmed", "integration_install_exit_code:7",
    ]) {
      const message = installFailureMessage(code);
      expect(message).toContain("bloqueadas nesta sessão");
      expect(message).toContain("reiniciar o app não confirma");
      expect(message).not.toContain("tentar novamente");
      expect(message.length).toBeLessThan(400);
    }
    expect(installFailureMessage("integration_install_timeout")).toContain("prazo de execução");
    expect(installFailureMessage("integration_install_stderr_too_large")).toContain("saída de diagnóstico");
    expect(installFailureMessage("integration_install_cleanup_unconfirmed")).toContain("encerramento do processo");
    expect(installFailureMessage("integration_install_reconciliation_required")).toContain("tentativa anterior");
  });

  it("asks only for another query when the receipt already confirmed the installation", () => {
    const message = installFailureMessage("integration_install_applied_snapshot_unavailable");
    expect(message).toContain("confirmou a aplicação");
    expect(message).toContain("Consulte novamente o diagnóstico");
    expect(message).toContain("não reinstale");
    expect(message).not.toContain("tentar outra instalação");
    expect(message).not.toContain("bloqueadas");
  });

  it("does not authorize a retry or assert a known process state for unknown failures", () => {
    const message = installFailureMessage("unrecognized-before-or-after-start");
    expect(message).toContain("Não repita a aplicação até esclarecer o resultado");
    expect(message).not.toContain("tentar novamente");
    expect(message).not.toContain("não foi iniciado");
    expect(message).not.toContain("bloqueadas nesta sessão");
  });
});

describe("installer recovery without repeated side effects", () => {
  it("allows only a fresh review when native preflight failed before any installer started", () => {
    const code = "integration_preflight_unavailable";
    expect(installFailureRecovery(code)).toBe("review");
    expect(installFailureRecovery(new Error(code))).toBe("review");
    expect(installFailureMessage(code)).toContain("O instalador não foi iniciado");
    expect(installFailureMessage(code)).toContain("revise um novo plano");
    expect(installFailureMessage(code)).not.toContain("alterações parciais");
  });

  it("requires explicit plan review for a changed plan or a proven failure to start", () => {
    expect(installFailureRecovery("integration_plan_changed_review_again")).toBe("review");
    expect(installFailureRecovery(new Error("integration_install_not_started"))).toBe("review");
  });

  it("waits for a running attempt and only refreshes after a confirmed receipt", () => {
    expect(installFailureRecovery("integration_install_busy")).toBe("wait");
    expect(installFailureRecovery("integration_install_applied_snapshot_unavailable")).toBe("refresh");
  });

  it("does not release post-start uncertainty or unknown errors for a new install", () => {
    for (const error of [
      "integration_install_timeout", "integration_install_stderr_too_large",
      "integration_install_cleanup_unconfirmed", "integration_install_reconciliation_required",
      "integration_install_output_unavailable", "integration_install_no_exit_code",
      "integration_install_invalid_json", "integration_install_response_too_large",
      "integration_install_receipt_unconfirmed", "integration_install_exit_code:7",
      "runtime_not_started", "integration_install_not_started ",
      "integration_preflight_unavailable ", "integration_preflight_unavailable: extra",
      new Error("integration_install_not_started: extra"), { message: "integration_install_not_started" },
      "__proto__", "constructor", null, "x".repeat(100_000),
    ]) expect(installFailureRecovery(error)).toBe("reconcile");
  });
});

describe("typed partial install diagnostics", () => {
  const partial = (overrides: Record<string, unknown> = {}) => ({
    schema: "simplicio.desktop-install-error/v1",
    code: "integration_install_exit_code:1",
    diagnostic: {
      schema: "simplicio.desktop-install-diagnostic/v1", status: "partial",
      failedSteps: ["hermes"], unknownFailedSteps: 0,
    },
    ...overrides,
  });

  it("shows only reviewed step labels without releasing retry protection", () => {
    const message = installFailureMessage(partial());
    expect(message).toContain("Hermes");
    expect(message).toContain("código 1.");
    expect(message).toContain("bloqueadas nesta sessão");
    expect(installFailureRecovery(partial())).toBe("reconcile");
  });

  it("never reflects unknown names, details, paths, or an inconsistent no-start claim", () => {
    const secret = "DO_NOT_LEAK /private/test-user";
    for (const diagnostic of [
      { schema: "simplicio.desktop-install-diagnostic/v1", status: "partial", failedSteps: [secret], unknownFailedSteps: 0 },
      { schema: "simplicio.desktop-install-diagnostic/v1", status: "partial", failedSteps: ["hermes", "hermes"], unknownFailedSteps: 0 },
      { schema: "simplicio.desktop-install-diagnostic/v1", status: "partial", failedSteps: ["hermes"], unknownFailedSteps: 129 },
      { schema: "wrong", status: "partial", failedSteps: ["hermes"], unknownFailedSteps: 0 },
    ]) {
      const error = partial({ diagnostic });
      expect(installFailureMessage(error)).not.toContain(secret);
      expect(installFailureMessage(error)).not.toContain("Hermes");
      expect(installFailureRecovery(error)).toBe("reconcile");
    }
    const inconsistent = partial({ code: "integration_install_not_started" });
    expect(installFailureRecovery(inconsistent)).toBe("reconcile");
    expect(installFailureMessage(inconsistent)).not.toContain("não foi iniciado");
    expect(installFailureMessage(partial({ code: "integration_install_exit_code:0" }))).not.toContain("Hermes");
  });

  it("supports typed preflight errors and generic unknown failed steps", () => {
    expect(installFailureRecovery({ schema: "simplicio.desktop-install-error/v1", code: "integration_preflight_unavailable" })).toBe("review");
    const error = partial({ diagnostic: {
      schema: "simplicio.desktop-install-diagnostic/v1", status: "partial",
      failedSteps: [], unknownFailedSteps: 2,
    } });
    expect(installFailureMessage(error)).toContain("2 etapa(s) não identificada(s)");
    expect(installFailureRecovery(error)).toBe("reconcile");
  });
});

describe("durable install-attempt diagnostics", () => {
  it("restores a sanitized partial failure after an app restart", () => {
    const error = {
      schema: "simplicio.desktop-install-error/v1",
      code: "integration_install_exit_code:1",
      diagnostic: {
        schema: "simplicio.desktop-install-diagnostic/v1",
        status: "partial",
        failedSteps: ["hermes"],
        unknownFailedSteps: 1,
      },
    };
    const result = parseInstallAttemptDiagnostic({
      schema: "simplicio.desktop-install-attempt/v1",
      status: "reconciliation_required",
      error,
    });
    expect(result.status).toBe("reconciliation_required");
    expect(installFailureMessage(result.error)).toContain("Hermes");
    expect(installFailureMessage(result.error)).toContain("código 1");
    expect(installFailureRecovery(result.error)).toBe("reconcile");
  });

  it("accepts only a closed clear state and rejects injected persisted details", () => {
    expect(parseInstallAttemptDiagnostic({
      schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: null,
    })).toEqual({ status: "clear", error: null });
    for (const value of [
      { schema: "wrong", status: "clear", error: null },
      { schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: { token: "DO_NOT_LEAK" } },
      { schema: "simplicio.desktop-install-attempt/v1", status: "reconciliation_required", error: { schema: "simplicio.desktop-install-error/v1", code: "DO_NOT_LEAK" } },
      { schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: null, extra: "DO_NOT_LEAK" },
    ]) expect(() => parseInstallAttemptDiagnostic(value)).toThrow("integration_install_diagnostic_invalid");
  });
});
