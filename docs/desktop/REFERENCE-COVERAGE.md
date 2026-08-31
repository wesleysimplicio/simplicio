# Desktop: cobertura das referências

Este mapa descreve as telas e os contratos presentes no código. Cobertura visual não significa equivalência funcional com outro produto, autorização para executar agentes ou validação nativa em todas as plataformas. Os screenshots privados e seus dados não fazem parte deste documento.

## Correspondência visual

- **Orca:** estrutura branca do workspace, projetos, navegação lateral pesquisável, grupos de preferências, inventários e relatórios. As seções têm conteúdo próprio, não apenas títulos diferentes.
- **Hermes Agent Desktop:** instalação orientada por etapas, revisão do plano e indicação de progresso/resultado. O efeito continua limitado ao contrato de configuração do Runtime.
- **Claude:** entrada simples, identidade Simplicio e login externo. A autenticação e o estado de acesso vêm do Runtime, não de uma simulação visual.
- **Referência de extração/atualização:** o Desktop mostra etapas da consulta real de metadados. Não simula extração, instalação automática ou troca do aplicativo.

## Telas e fluxos existentes

Os identificadores abaixo são views internas; login é um estado de acesso e atualizações é um diálogo global, não uma rota de página.

| Superfície | Caminho implementado e limite |
| --- | --- |
| Login / acesso | Login externo, nova consulta, estado da assinatura e saída pelo Runtime. Falha de autenticação não vira acesso ativo; login Simplicio não autentica contas de LLMs. |
| `setup` | Revisão explícita do plano, aplicação e verificação posterior dos alvos revisados. Aplicar configuração não equivale a handshake confirmado nem a instalar todos os plugins nativos. |
| `home`, `project` | Navegação, histórico, atalhos locais e seleção de projeto. O seletor nativo valida uma pasta existente; adicioná-la exige confirmação. Não clona repositórios nem inicia agentes. |
| `agents`, `providers` | Inventário, filtros e estados separados de instalação, registro MCP e handshake. A visão de integrações oferece revisão/reparo; inventário não comprova sessão ativa no cliente. |
| `settings`, `diagnostics` | Conta, atualização da consulta, saída e diagnóstico oferecidos pelo Runtime. Sem cadastrar credenciais de outros serviços. |
| `tokens` | Consulta de uso por pasta, período e sessão; exportação local JSON/CSV do relatório consultado. Economia de contexto aparece separada do consumo registrado e de cobrança. |
| `general`, `shortcuts`, `models`, `activity` | Preferências locais existentes, orientação de teclado, inventário e atividade do último snapshot. Metadados não renovam a consulta nem concedem autoridade. |
| Check for Updates… | Menu e diálogo global consultam metadados públicos e procuram pacote Desktop compatível. A ação abre a página de releases para obter o instalador; instalação manual. Versão/pacote desconhecidos não produzem “atualizado”. |

## Novas rotas de preferências

Fonte canônica: [catálogo de navegação](../../apps/desktop/src/reference_screens.ts). O grupo e o título seguem esse catálogo; a implementação está em [ReferenceSettingsScreen](../../apps/desktop/src/screens/ReferenceSettingsScreen.tsx).

| Grupo | Rota — tela | Capacidade disponível / limite explícito |
| --- | --- | --- |
| Capacidades | `provider-accounts` — Contas de IA | Cards de provedores e evidência MCP disponível; autenticação das contas não consultada. Sem campos de senha, chave ou cookie. |
| Capacidades | `orchestration` — Orquestração | Perfis reportados e links ao Bot Center/atividade. Limite de paralelismo não consultado; não admite nem inicia agentes. |
| Capacidades | `computer-use` — Uso do computador | Estado de sessão reportado e requisitos de permissão; esta tela não captura imagens nem controla aplicativos. |
| Capacidades | `voice` — Voz | Seções de ditado, dispositivo e modelo; captura, transcrição e download de modelos indisponíveis. |
| Configuração | `general-settings` — Geral | Links às preferências e conta existentes; inicialização automática nativa indisponível. |
| Configuração | `integrations` — Integrações de serviços | Cards de serviços de código/tarefas e navegação; conectar contas e importar tarefas indisponíveis. |
| Configuração | `mobile` — Simplicio Mobile | Requisitos de pareamento e dispositivos; sem QR fictício, token, relay ou cliente conectado presumido. |
| Fluxos | `artifacts` — Artefatos | Metadados reportados e links aos relatórios; abrir/exportar os arquivos desse inventário indisponível. |
| Fluxos | `share-skills` — Compartilhar skills | Nomes informados pelo Runtime; conteúdo, compartilhamento e publicação indisponíveis. |
| Fluxos | `git` — Git e código-fonte | Links a projetos e serviços; criação de worktrees, revisão Git, commit e push indisponíveis nesta tela. |
| Fluxos | `task-sources` — Fontes de tarefas | Seções expansíveis por teclado e links aos serviços; consultas de issues e preferências sem efeito indisponíveis. |
| Fluxos | `terminal` — Terminal | Comandos fixos copiáveis para o terminal do usuário; sem PTY, execução ou leitura de histórico. |
| Fluxos | `quick-commands` — Comandos rápidos | Cópia explícita de comandos documentados, com espera limitada; copiar não executa e não coleta a saída. |
| Fluxos | `browser` — Navegador | Requisitos de sessão e links às ferramentas; navegador integrado, importação de cookies e automação indisponíveis. |
| Fluxos | `emulator` — Emulador mobile | Seções Android/iOS; detecção de SDKs, inventário de dispositivos e inicialização indisponíveis. |
| Fluxos | `floating` — Janela flutuante | Organização da janela e navegação existente; criar janela ou mantê-la à frente indisponível. |
| Interface | `input` — Entrada e edição | Orientação de teclado e links a atalhos/voz; opções de editor sem contrato indisponíveis. |
| Interface | `notifications` — Notificações | Atividade disponível e requisitos; permissão nativa não consultada, envio de teste indisponível. |
| Hosts remotos | `hosts` — Hosts SSH | Requisitos e acesso aos projetos locais; não lê chaves, conecta SSH nem cria hosts. |
| Hosts remotos | `servers` — Servidores Simplicio | Estado local reportado; descoberta, autenticação e conexão de servidores remotos indisponíveis. |
| Privacidade e segurança | `permissions` — Permissões do sistema | Orientação por recurso; permissões não consultadas, não presumidas concedidas ou negadas. Solicitações nativas indisponíveis. |
| Privacidade e segurança | `privacy` — Privacidade e telemetria | Escopo dos metadados e links a diagnóstico/preferências; não presume estado da telemetria nem oferece exclusão de dados. |
| Avançado | `advanced` — Avançado | Evidência do Runtime e comandos copiáveis; alteração de proxy/rede indisponível. |
| Experimental | `experimental` — Experimental | Cards com navegação para recursos relacionados, sem switches que finjam ativação. |
| Experimental | `plugins` — Plugins | Catálogo pesquisável e inventário de skills reportadas, separados da instalação. Instalação/ativação automática dos plugins nativos de harnesses/IDEs indisponível nesta tela. |

Controles sem contrato ficam desabilitados com explicação. Navegação, busca, filtros, expansão de seções, atualização explícita do snapshot e cópia de comandos têm ações implementadas. A prévia é identificada como tal; seus exemplos não comprovam conexão, instalação ou economia. As novas telas não fornecem execução de agentes, pareamento Mobile, controle do computador, voz, SSH ou instalação automática de plugins. A atualização não possui downloader nativo com extração, validação e troca automática do aplicativo (*stage/swap*).

## Pastas automáticas e relatórios

O relatório de tokens procura **candidatos**, separando dois marcadores:

| Marcador dentro do projeto | Significado da descoberta |
| --- | --- |
| `.simplicio/token-usage.sqlite3` | Possível banco de uso; verifica somente tamanho/cabeçalho SQLite, não tabelas ou totais. |
| `.simplicio/ledger/savings-events.jsonl` | Possível ledger de contexto; verifica somente um prefixo reconhecível, não a validade dos eventos. |

- A busca usa `Projetos`, `Projects` e `Desktop` da pasta pessoal, quando acessíveis, além do repositório nativo configurado quando aceito. **Não percorre toda a pasta pessoal** nem aceita a raiz do sistema como repositório de varredura.
- Limites globais: profundidade de 5 níveis, 4.000 diretórios, 40.000 entradas e 64 resultados. O orçamento de diretórios/entradas é dividido entre os locais. Cada local é lido num subprocesso independente: prazo cooperativo de 2 segundos durante a varredura e limite de captura de 3 segundos, com tentativa de encerramento/reap limitada. Uma chamada de filesystem presa não ocupa indefinidamente um worker do Desktop. Se o sistema não confirmar o término do filho, o handle é retido e novas capturas ficam bloqueadas; não se presume cancelamento concluído.
- Resultados de locais concluídos são preservados quando outro local não responde. A lista informa os locais não concluídos, sem exigir que o usuário conceda permissões automaticamente. Os contadores de varredura referem-se às respostas concluídas, não à atividade desconhecida de um filho interrompido.
- Não segue links simbólicos; exclui dependências, caches e saídas de build. Lê apenas prefixos dos marcadores (até 512 bytes; 100 no SQLite), não documentos do projeto. Limites, diretórios inacessíveis e outras omissões são apresentados como descoberta parcial.
- A ordenação usa a modificação do marcador, não a data de uma sessão. Sem seleção prévia, pode selecionar o primeiro candidato e consultar os relatórios; uma escolha manual não é substituída. O seletor de pasta e o caminho manual continuam disponíveis para locais fora da busca.
- **Marcador encontrado não prova uso ou economia.** Os números só vêm após a consulta e validação pelo Runtime. O relatório de contexto exige ledger íntegro/promovível; mantém a qualificação da evidência e separa contexto de uso. Falha, ausência de amostras ou dado indisponível não significam consumo zero nem cobrança confirmada.

Contratos: [descoberta nativa](../../apps/desktop/src-tauri/src/project_usage.rs), [seleção de pastas](../../apps/desktop/src/components/TokenProjects.tsx), [relatório de uso](../../apps/desktop/src/screens/TokensScreen.tsx), [projeção de contexto](../../apps/desktop/src-tauri/src/context_report.rs), [montagem das telas](../../apps/desktop/src/App.tsx) e [manual de release](../RELEASE_RUNBOOK.md).
