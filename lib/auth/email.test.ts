import { describe, it, expect } from "vitest";
import { normalizeEmail } from "./email";

describe("normalizeEmail", () => {
  it("strips plus-addressing: user+1@gmail.com → user@gmail.com", () => {
    expect(normalizeEmail("user+1@gmail.com")).toBe("user@gmail.com");
  });

  it("strips plus-addressing: user+foo@domain.com → user@domain.com", () => {
    expect(normalizeEmail("user+foo@domain.com")).toBe("user@domain.com");
  });

  it("leaves email without plus unchanged", () => {
    expect(normalizeEmail("user@domain.com")).toBe("user@domain.com");
  });

  it("normalizes to lowercase", () => {
    expect(normalizeEmail("User+Tag@Domain.COM")).toBe("user@domain.com");
  });

  it("trims whitespace", () => {
    expect(normalizeEmail("  user+1@gmail.com  ")).toBe("user@gmail.com");
  });

  it("handles multiple plus signs - takes first segment", () => {
    expect(normalizeEmail("user+foo+bar@gmail.com")).toBe("user@gmail.com");
  });

  it("handles empty string", () => {
    expect(normalizeEmail("")).toBe("");
  });

  it("handles invalid input - no @", () => {
    expect(normalizeEmail("usergmail.com")).toBe("usergmail.com");
  });

  it("handles plus at end of local part", () => {
    expect(normalizeEmail("user+@gmail.com")).toBe("user@gmail.com");
  });
});
