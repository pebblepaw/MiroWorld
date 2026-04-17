type HostedEnvAliases = {
  VITE_SUPABASE_PUBLISHABLE_KEY: string;
  VITE_SUPABASE_URL: string;
};

export function resolveHostedViteEnvAliases(env: Record<string, string | undefined>): HostedEnvAliases {
  return {
    VITE_SUPABASE_PUBLISHABLE_KEY:
      env.VITE_SUPABASE_PUBLISHABLE_KEY
      || env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
      || env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      || "",
    VITE_SUPABASE_URL: env.VITE_SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL || "",
  };
}

export function resolveHostedViteDefine(env: Record<string, string | undefined>) {
  const aliases = resolveHostedViteEnvAliases(env);

  return {
    "import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY": JSON.stringify(aliases.VITE_SUPABASE_PUBLISHABLE_KEY),
    "import.meta.env.VITE_SUPABASE_URL": JSON.stringify(aliases.VITE_SUPABASE_URL),
  };
}
