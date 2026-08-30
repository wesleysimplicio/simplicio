import type { DesktopSnapshot } from "./contracts";

export type CapabilityCategory = "Create" | "Explore" | "Act" | "Build" | "Learn";

export interface CapabilityDescriptor {
  id: string;
  category: CapabilityCategory;
  name: string;
  description: string;
  available: boolean;
  requiresApproval: boolean;
  reasonCode: string;
}

export interface CapabilityRegistry {
  schema: "capability.registry/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  capabilities: CapabilityDescriptor[];
  reasonCode: "capability.registry_ready" | "capability.registry_unavailable";
}

export function createCapabilityRegistry(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): CapabilityRegistry {
  const descriptions: Array<Pick<CapabilityDescriptor, "id" | "category" | "name" | "description" | "requiresApproval">> = [
    { id: "video.studio", category: "Create", name: "Video Studio", description: "Criar vídeos com um Work Item observável.", requiresApproval: true },
    { id: "browser.research", category: "Explore", name: "Browser & Research", description: "Pesquisar com evidência e artifacts vinculados.", requiresApproval: true },
    { id: "computer.use", category: "Act", name: "Computer", description: "Operar uma sessão Computer com lease explícito.", requiresApproval: true },
    { id: "build.workspace", category: "Build", name: "Files, PDF & Code", description: "Construir em um Workspace governado.", requiresApproval: true },
    { id: "teach.compiler", category: "Learn", name: "Teach Simplicio", description: "Gravar e revisar uma rotina reproduzível.", requiresApproval: true },
  ];
  return {
    schema: "capability.registry/v1",
    generatedAt,
    source: snapshot.source,
    capabilities: descriptions.map((capability) => ({
      ...capability,
      available: false,
      reasonCode: "desktop_capability_dispatch_unavailable",
    })),
    reasonCode: "capability.registry_unavailable",
  };
}
