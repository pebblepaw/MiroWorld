import { createClient, type SupabaseClient } from "@supabase/supabase-js";

type HostedSupabaseEnv = {
  publishableKey: string;
  url: string;
};

let cachedClient: SupabaseClient | null = null;

export function getHostedSupabaseEnv(): HostedSupabaseEnv {
  const url = String(import.meta.env.VITE_SUPABASE_URL || "").trim();
  const publishableKey = String(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || "").trim();

  return {
    publishableKey,
    url,
  };
}

export function getSupabaseConfigurationError(): string | null {
  const { url, publishableKey } = getHostedSupabaseEnv();

  if (!url || !publishableKey) {
    return "Missing Supabase configuration. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY for the hosted frontend.";
  }

  return null;
}

export function getSupabaseClient(): SupabaseClient | null {
  if (cachedClient) {
    return cachedClient;
  }

  const env = getHostedSupabaseEnv();
  if (!env.url || !env.publishableKey) {
    return null;
  }

  cachedClient = createClient(env.url, env.publishableKey);
  return cachedClient;
}

export async function getSupabaseAccessToken(): Promise<string | null> {
  const client = getSupabaseClient();
  if (!client) {
    return null;
  }

  const { data, error } = await client.auth.getSession();
  if (error) {
    throw error;
  }

  return data.session?.access_token ?? null;
}
