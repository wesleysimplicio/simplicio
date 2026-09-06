export type RuntimeOperation = "query" | "install" | "login" | "logout";

const REASONS: Readonly<Record<string, string>> = {
  runtime_not_started: "Não foi possível iniciar um comando do Simplicio Runtime.",
  runtime_query_timeout: "Uma etapa do Runtime ultrapassou o prazo de 20 segundos.",
  runtime_oauth_timeout: "O login ultrapassou o prazo de 3 minutos sem confirmação.",
  runtime_auth_busy: "Já existe uma entrada ou saída de conta em andamento neste aplicativo. Aguarde a conclusão antes de tentar novamente.",
  runtime_auth_state_unavailable: "O estado da autenticação não pôde ser confirmado. Reinicie o Desktop antes de tentar novamente.",
  runtime_auth_only_unsupported: "O Runtime não oferece login separado da instalação. Atualize o Simplicio Desktop para entrar com Google com segurança.",
  runtime_auth_result_unconfirmed: "O Runtime não confirmou um login sem configuração automática.",
  runtime_install_timeout: "A instalação ultrapassou o prazo de 5 minutos sem confirmação. Não repita a instalação sem esclarecer o resultado.",
  runtime_stdout_limit: "A resposta do Runtime ultrapassou o limite permitido.",
  runtime_stderr_limit: "A saída de diagnóstico do Runtime ultrapassou o limite permitido.",
  runtime_output_unavailable: "Não foi possível obter a saída de um comando do Runtime.",
  runtime_process_cleanup_unconfirmed: "Não foi possível confirmar o encerramento de um processo do Runtime. Novos comandos do Runtime estão bloqueados enquanto esse processo permanecer pendente.",
  desktop_snapshot_timeout: "A consulta do Desktop não respondeu no prazo. O Runtime ainda pode estar concluindo a consulta.",
  runtime_install_package_unavailable: "O Runtime empacotado não foi encontrado neste aplicativo.",
  runtime_install_package_invalid: "O Runtime empacotado não passou na validação.",
  runtime_install_home_unavailable: "A pasta local do usuário não está disponível para instalar o Runtime.",
  runtime_install_path_invalid: "O destino local do Runtime não passou na validação de segurança.",
  runtime_install_directory_unavailable: "Não foi possível preparar a pasta privada do Runtime.",
  runtime_install_permissions_failed: "Não foi possível aplicar permissões privadas ao Runtime.",
  runtime_install_read_failed: "Não foi possível ler o Runtime durante a instalação.",
  runtime_install_busy: "Outra instalação do Runtime está em andamento.",
  runtime_install_lock_failed: "Não foi possível proteger esta instalação contra concorrência.",
  runtime_install_stage_failed: "Não foi possível preparar o Runtime no destino local.",
  runtime_install_backup_failed: "Não foi possível preservar a versão anterior do Runtime.",
  runtime_install_publish_failed: "Não foi possível ativar o Runtime preparado. Consulte novamente o estado antes de repetir.",
  runtime_install_publish_failed_restored: "Não foi possível ativar o Runtime preparado. Consulte novamente o estado antes de repetir.",
  runtime_install_publish_failed_removed: "Não foi possível ativar o Runtime preparado. Consulte novamente o estado antes de repetir.",
  runtime_install_post_replace_failed: "A ativação do Runtime falhou depois da troca. Consulte novamente o estado antes de repetir.",
  runtime_install_post_replace_failed_restored: "A ativação do Runtime falhou depois da troca. Consulte novamente o estado antes de repetir.",
  runtime_install_post_replace_failed_removed: "A ativação do Runtime falhou depois da troca. Consulte novamente o estado antes de repetir.",
  runtime_install_rollback_failed: "Não foi possível confirmar a restauração da versão anterior do Runtime.",
  runtime_install_verification_failed: "O Runtime instalado não passou na validação final.",
  runtime_install_version_invalid: "A versão informada pelo Runtime não é um SemVer válido.",
  runtime_install_installed_version_unknown: "A versão do Runtime já instalado não pôde ser confirmada; ele não será substituído automaticamente.",
  runtime_install_same_version_mismatch: "O Runtime instalado tem a mesma versão do pacote, mas conteúdo diferente; ele não será sobrescrito automaticamente.",
  runtime_install_newer_unverified: "Existe um Runtime local mais novo sem proveniência oficial confirmada. Ele foi preservado, mas o Desktop continuará usando apenas o Runtime assinado que acompanha o aplicativo.",
  runtime_install_managed_newer_preserved: "Existe um Runtime local mais novo com recibo do Desktop. Ele foi preservado, mas os comandos continuam usando apenas o Runtime assinado que acompanha o aplicativo.",
  runtime_install_managed_unverified: "Existe um Runtime local diferente sem recibo verificável do Desktop. Ele foi preservado e exige recuperação explícita.",
  runtime_install_receipt_invalid: "O recibo local do Runtime não passou na validação de segurança.",
  runtime_install_receipt_read_failed: "Não foi possível ler com segurança o recibo local do Runtime.",
  runtime_install_receipt_write_failed: "Não foi possível gravar de forma durável o recibo local do Runtime.",
  runtime_install_precondition_changed: "O Runtime local mudou durante a preparação; a instalação foi interrompida sem sobrescrever o novo estado.",
  runtime_install_snapshot_invalid: "O Runtime instalado não devolveu um estado atual válido.",
  runtime_install_unavailable: "A operação nativa de instalação do Runtime não está disponível.",
  runtime_install_reconciliation_required: "A última tentativa de instalação não teve resultado confirmado. Consulte e reconcilie o estado antes de tentar novamente.",
  runtime_install_reconciliation_unavailable: "Não foi possível esclarecer o estado da última instalação. Nenhuma nova tentativa foi iniciada.",
  runtime_install_journal_unavailable: "Não foi possível registrar com segurança o estado da instalação. Nenhuma alteração foi iniciada.",
  runtime_install_reconciliation_invalid: "A resposta de reconciliação do Runtime não passou na validação.",
};

const NEXT_STEPS: Readonly<Record<RuntimeOperation, string>> = {
  query: "Verifique o Runtime e consulte novamente o estado; nenhum resultado atual foi confirmado.",
  install: "Nenhum plugin foi alterado. Inicie uma nova tentativa somente pelo botão desta tela.",
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
