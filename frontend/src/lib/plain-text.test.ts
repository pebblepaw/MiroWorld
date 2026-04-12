import { describe, expect, it } from "vitest";

import { formatPlainText } from "@/lib/plain-text";

describe("formatPlainText", () => {
  it("strips markdown emphasis and list markers while preserving readable text", () => {
    const result = formatPlainText("**Cost relief** matters.\n- Keep signup simple.\n1. Avoid long queues.");

    expect(result).toBe("Cost relief matters.\nKeep signup simple.\nAvoid long queues.");
  });
});