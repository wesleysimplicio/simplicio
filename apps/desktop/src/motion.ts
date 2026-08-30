import { designTokens } from "./design_tokens";

export type MotionKind = keyof typeof designTokens.motion;

export interface MotionPolicy {
  reduced: boolean;
  duration: (kind: MotionKind) => string;
  decorativeAnimation: "enabled" | "disabled";
}

export function createMotionPolicy(reduced: boolean): MotionPolicy {
  return {
    reduced,
    duration: (kind) => reduced ? "1ms" : designTokens.motion[kind],
    decorativeAnimation: reduced ? "disabled" : "enabled",
  };
}
