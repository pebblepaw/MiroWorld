import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveHostedViteDefine } from "@/lib/hosted-env";

describe("Vite hosted env aliases", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("maps NEXT_PUBLIC Supabase env names onto VITE aliases for frontend code", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://project.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key");

    expect(resolveHostedViteDefine(process.env as Record<string, string | undefined>)).toMatchObject({
      "import.meta.env.VITE_SUPABASE_URL": JSON.stringify("https://project.supabase.co"),
      "import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY": JSON.stringify("sb_publishable_test_key"),
    });
  });
});
