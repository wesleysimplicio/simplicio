import { describe, expect, it } from "vitest";
import { createMotionPolicy } from "./motion";

describe("calm motion policy", () => {
  it("uses named durations for meaningful state changes", () => {
    const motion = createMotionPolicy(false);
    expect(motion.duration("instant")).toBe("100ms");
    expect(motion.duration("fast")).toBe("160ms");
    expect(motion.duration("standard")).toBe("220ms");
    expect(motion.duration("deliberate")).toBe("320ms");
    expect(motion.duration("ambient")).toBe("3200ms");
  });

  it("removes decorative motion without removing state transitions", () => {
    const motion = createMotionPolicy(true);
    expect(motion.duration("standard")).toBe("1ms");
    expect(motion.decorativeAnimation).toBe("disabled");
  });
});
