import { describe, expect, it } from "vitest";

import { formatPlainText } from "@/lib/plain-text";

describe("formatPlainText", () => {
  it("strips markdown emphasis and list markers while preserving readable text", () => {
    const result = formatPlainText("**Cost relief** matters.\n- Keep signup simple.\n1. Avoid long queues.");

    expect(result).toBe("Cost relief matters.\nKeep signup simple.\nAvoid long queues.");
  });

  it("strips stray inline asterisk markers used as fake bullets", () => {
    const result = formatPlainText(
      "AI-Powered Social Media Simulation: AI citizens interact by posting. * Direct Interaction: Enables users to chat directly with agents.",
    );

    expect(result).toBe(
      "AI-Powered Social Media Simulation: AI citizens interact by posting. Direct Interaction: Enables users to chat directly with agents.",
    );
  });

  it("strips inline hashtag markers while keeping the tag text readable", () => {
    const result = formatPlainText(
      "We should support local jobs. #ProtectWorkers #AIReadiness matters in every town hall.",
    );

    expect(result).toBe(
      "We should support local jobs. ProtectWorkers AIReadiness matters in every town hall.",
    );
  });
});
