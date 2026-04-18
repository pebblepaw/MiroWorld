import type { PropsWithChildren } from "react";
import { createContext, useContext, useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { getSupabaseClient, getSupabaseConfigurationError } from "@/lib/supabase-client";

type PasswordCredentials = {
  email: string;
  password: string;
};

type AuthContextValue = {
  configurationError: string | null;
  isLoading: boolean;
  session: Session | null;
  signInWithPassword: (credentials: PasswordCredentials) => Promise<{ session: Session | null }>;
  signOut: () => Promise<void>;
  signUpWithPassword: (credentials: PasswordCredentials) => Promise<{ session: Session | null }>;
  user: User | null;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function normalizeCredentials(credentials: PasswordCredentials): PasswordCredentials {
  return {
    email: credentials.email.trim(),
    password: credentials.password,
  };
}

async function registerHostedAccount(credentials: PasswordCredentials): Promise<void> {
  const response = await fetch("/api/v2/hosted/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });

  if (response.ok) {
    return;
  }

  let detail = "Unable to create a hosted account.";
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      detail = payload.detail.trim();
    }
  } catch {
    // Ignore non-JSON failures.
  }
  throw new Error(detail);
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [configurationError, setConfigurationError] = useState<string | null>(null);

  useEffect(() => {
    const client = getSupabaseClient();
    const missingConfig = getSupabaseConfigurationError();

    if (!client) {
      setConfigurationError(missingConfig);
      setIsLoading(false);
      return;
    }

    let mounted = true;
    setConfigurationError(missingConfig);

    void client.auth.getSession().then(({ data, error }) => {
      if (!mounted) {
        return;
      }

      if (error) {
        setConfigurationError(error.message);
      } else {
        setSession(data.session ?? null);
        setUser(data.session?.user ?? null);
      }

      setIsLoading(false);
    });

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!mounted) {
        return;
      }

      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setIsLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signUpWithPassword(credentials: PasswordCredentials) {
    const client = getSupabaseClient();
    if (!client) {
      throw new Error(getSupabaseConfigurationError() || "Supabase auth is unavailable.");
    }

    const { email, password } = normalizeCredentials(credentials);
    await registerHostedAccount({ email, password });
    return signInWithPassword({ email, password });
  }

  async function signInWithPassword(credentials: PasswordCredentials) {
    const client = getSupabaseClient();
    if (!client) {
      throw new Error(getSupabaseConfigurationError() || "Supabase auth is unavailable.");
    }

    const { email, password } = normalizeCredentials(credentials);
    const { data, error } = await client.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      throw error;
    }

    return {
      session: data.session ?? null,
    };
  }

  async function signOut() {
    const client = getSupabaseClient();
    if (!client) {
      return;
    }

    const { error } = await client.auth.signOut();
    if (error) {
      throw error;
    }
  }

  return (
    <AuthContext.Provider
      value={{
        configurationError,
        isLoading,
        session,
        signInWithPassword,
        signOut,
        signUpWithPassword,
        user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider.");
  }

  return context;
}
