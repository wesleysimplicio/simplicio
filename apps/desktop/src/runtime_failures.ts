export type RuntimeOperation = "query" | "login" | "logout";

const REASONS: Readonly<Record<string, string>> = {
  runtime_not_started: "Não foi possível iniciar um comando do Simplicio Runtime.",
  runtime_query_timeout: "Uma etapa do Runtime ultrapassou o prazo de 20 segundos.",
  runtime_oauth_timeout: "O login ultrapassou o prazo de 3 minutos sem confirmação.",
  runtime_install_timeout: "A instalação ultrapassou o prazo de 5 minutos sem confirmação. Não repita a instalação sem esclarecer o resultado.",
  runtime_stdout_limit: "A resposta do Runtime ultrapassou o limite permitido.",
  runtime_stderr_limit: "A saída de diagnóstico do Runtime ultrapassou o limite permitido.",
  runtime_output_unavailable: "Não foi possível obter a saída de um comando do Runtime.",
  runtime_process_cleanup_unconfirmed: "Não foi possível confirmar o encerramento de um processo do Runtime. Novos comandos do Runtime estão bloqueados enquanto esse processo permanecer pendente.",
  desktop_snapshot_timeout: "A consulta do Desktop não respondeu no prazo. O Runtime ainda pode estar concluindo a consulta.",
};

const NEXT_STEPS: Readonly<Record<RuntimeOperation, string>> = {
  query: "Verifique o Runtime e consulte novamente o estado; nenhum resultado atual foi confirmado.",
  login: "O resultado final do login não foi confirmado. Consulte o estado da conta antes de iniciar outro login.",
  logout: "A saída da conta não foi confirmada. Consulte o estado da conta antes de repetir a ação.",
};

/** Keep native output out of UI errors, including when its command phase is unknown. */
export function runtimeFailureMessage(error: unknown, operation: RuntimeOperation = "query"): string {
  const code = typeof error === "string" ? error : error instanceof Error ? error.message : "";
  const reason = typeof code === "string" && code.length <= 100 && Object.prototype.hasOwnProperty.call(REASONS, code)
    ? REASONS[code] : "Não foi possível confirmar o resultado do Simplicio Runtime.";
  // Login/logout run an action followed by a query. A spawn failure may belong to
  // that later query, so it never proves that the account action did not start.
  return `${reason} ${NEXT_STEPS[operation]}`;
}
