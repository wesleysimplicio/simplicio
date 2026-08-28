export const locale = "pt-BR" as const;

export const copy = {
  "nav.home": "Início",
  "nav.providers": "Providers",
  "nav.activity": "Atividade",
  "nav.memory": "Memória",
  "nav.settings": "Configurações",
  "provider.connected": "Conectado",
  "provider.registered": "Registrado",
  "provider.detected": "Detectado",
  "provider.needs_attention": "Requer atenção",
  "provider.not_installed": "Não instalado",
} as const;

export type CopyKey = keyof typeof copy;

export function t(key: CopyKey): string {
  return copy[key];
}
