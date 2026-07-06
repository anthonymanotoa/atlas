import { describe, expect, it } from "vitest";
import { ACTION_META, fitTone } from "./index";

describe("fitTone (tokens v2)", () => {
  it("devuelve tokens semánticos v2, nunca el compat layer --color-*", () => {
    expect(fitTone(90)).toBe("var(--success)");
    expect(fitTone(70)).toBe("var(--primary)");
    expect(fitTone(40)).toBe("var(--muted-foreground)");
    expect(fitTone(null)).toBe("var(--muted-foreground)");
    expect(fitTone(undefined)).toBe("var(--muted-foreground)");
  });
});

describe("ACTION_META (tokens v2)", () => {
  it("cada tono es un var(--token) semántico, sin --color-*", () => {
    for (const meta of Object.values(ACTION_META)) {
      expect(meta.tone).toMatch(/^var\(--(accent2|info|success|warning)\)$/);
    }
  });
});
