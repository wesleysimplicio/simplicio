/** Navigation coverage for the supplied Orca references; availability is owned by each real contract. */
export const REFERENCE_SCREENS = [
  { id: "provider-accounts", label: "Contas de IA", group: "CAPACIDADES", description: "Provedores, modelos e autenticação gerenciada pelos seus agentes." },
  { id: "orchestration", label: "Orquestração", group: "CAPACIDADES", description: "Execução governada, agentes e evidências do Simplicio Loop." },
  { id: "computer-use", label: "Uso do computador", group: "CAPACIDADES", description: "Automação de aplicativos, ferramentas e permissões do sistema." },
  { id: "voice", label: "Voz", group: "CAPACIDADES", description: "Entrada de áudio, transcrição e modelos de voz." },
  { id: "general-settings", label: "Geral", group: "CONFIGURAÇÃO", description: "Preferências do aplicativo e ambiente de execução." },
  { id: "integrations", label: "Integrações de serviços", group: "CONFIGURAÇÃO", description: "GitHub, GitLab, Linear e Jira, separados das conexões MCP." },
  { id: "mobile", label: "Simplicio Mobile", group: "CONFIGURAÇÃO", description: "Dispositivos e pareamento com este computador." },
  { id: "artifacts", label: "Artefatos", group: "FLUXOS", description: "Relatórios, diagnósticos e arquivos produzidos pelo Runtime." },
  { id: "share-skills", label: "Compartilhar skills", group: "FLUXOS", description: "Skills disponíveis e seus limites de instalação e compartilhamento." },
  { id: "git", label: "Git e código-fonte", group: "FLUXOS", description: "Projetos locais, repositórios e revisão de alterações." },
  { id: "task-sources", label: "Fontes de tarefas", group: "FLUXOS", description: "Origem das tarefas de GitHub, GitLab, Linear e Jira." },
  { id: "terminal", label: "Terminal", group: "FLUXOS", description: "CLI local e comandos explícitos do Simplicio." },
  { id: "quick-commands", label: "Comandos rápidos", group: "FLUXOS", description: "Comandos documentados para consulta e diagnóstico." },
  { id: "browser", label: "Navegador", group: "FLUXOS", description: "Abertura de links, sessão e automação de navegação." },
  { id: "emulator", label: "Emulador mobile", group: "FLUXOS", description: "Dispositivos de desenvolvimento e ambientes de teste." },
  { id: "floating", label: "Janela flutuante", group: "FLUXOS", description: "Espaço de trabalho e organização das janelas." },
  { id: "input", label: "Entrada e edição", group: "INTERFACE", description: "Navegação por teclado, campos e comportamento de edição." },
  { id: "notifications", label: "Notificações", group: "INTERFACE", description: "Avisos do aplicativo e disponibilidade de notificações nativas." },
  { id: "hosts", label: "Hosts SSH", group: "HOSTS REMOTOS", description: "Conexões remotas explícitas e seus requisitos de segurança." },
  { id: "servers", label: "Servidores Simplicio", group: "HOSTS REMOTOS", description: "Runtime local e disponibilidade de servidores remotos." },
  { id: "permissions", label: "Permissões do sistema", group: "PRIVACIDADE E SEGURANÇA", description: "Microfone, câmera, tela, acessibilidade e acesso local." },
  { id: "privacy", label: "Privacidade e telemetria", group: "PRIVACIDADE E SEGURANÇA", description: "Dados locais, redação e evidências compartilhadas." },
  { id: "advanced", label: "Avançado", group: "AVANÇADO", description: "Compatibilidade, rede e diagnóstico do Runtime." },
  { id: "experimental", label: "Experimental", group: "EXPERIMENTAL", description: "Recursos que dependem de contratos ainda não disponíveis." },
  { id: "plugins", label: "Plugins", group: "EXPERIMENTAL", description: "Pacotes do Simplicio para os seus agentes e IDEs." },
] as const;

export type ReferenceSettingsView = typeof REFERENCE_SCREENS[number]["id"];

export function isReferenceSettingsView(view: string): view is ReferenceSettingsView {
  return REFERENCE_SCREENS.some((screen) => screen.id === view);
}

export const REFERENCE_LABELS = Object.fromEntries(REFERENCE_SCREENS.map((screen) => [screen.id, screen.label])) as Record<ReferenceSettingsView, string>;
