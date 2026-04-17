import type { FormEvent } from "react";
import { useState } from "react";
import { ArrowRight, CheckCircle2, LockKeyhole, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";

type AuthMode = "sign-up" | "log-in";

const BENEFITS = [
  "Supabase auth gate for the hosted workspace",
  "Shared Gemini runtime with no personal API key setup",
  "Same five-screen simulation flow after login",
];

export default function HostedEntry() {
  const { configurationError, signInWithPassword, signUpWithPassword } = useAuth();
  const [mode, setMode] = useState<AuthMode>("sign-up");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setFeedback(null);

    try {
      if (mode === "sign-up") {
        const result = await signUpWithPassword({ email, password });
        setFeedback(
          result.session
            ? "Account created. Redirecting you into the hosted workspace."
            : "Account created. Check your inbox to confirm your email before logging in.",
        );
        return;
      }

      await signInWithPassword({ email, password });
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Unable to complete authentication.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-6 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="flex items-center justify-between gap-4">
          <div>
            <p className="label-meta">Hosted MVP</p>
            <h1 className="text-page-title">MiroWorld</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/pricing" className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
              View pricing
            </Link>
            <div className="hidden rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:block">
              Supabase + Zep hosted preview
            </div>
          </div>
        </header>

        <main className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="surface-card relative overflow-hidden p-8 sm:p-10">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-[hsl(var(--data-blue))] to-[hsl(var(--data-cyan))]" />
            <div className="grid gap-8 lg:grid-cols-[1fr_auto]">
              <div className="space-y-6">
                <div className="space-y-3">
                  <p className="label-meta">Hosted simulation console</p>
                  <h2 className="max-w-xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                    Launch hosted simulations without BYOK setup.
                  </h2>
                  <p className="max-w-2xl text-base text-muted-foreground sm:text-lg">
                    This branch uses Supabase auth at the front door, keeps pricing informational, and assumes a shared
                    Gemini server runtime once a team member signs in.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-border bg-muted/40 p-4">
                    <p className="label-meta">Auth</p>
                    <p className="mt-2 text-sm text-foreground">Email + password via hosted Supabase.</p>
                  </div>
                  <div className="rounded-2xl border border-border bg-muted/40 p-4">
                    <p className="label-meta">Runtime</p>
                    <p className="mt-2 text-sm text-foreground">Shared Gemini runtime with no personal API key.</p>
                  </div>
                  <div className="rounded-2xl border border-border bg-muted/40 p-4">
                    <p className="label-meta">Flow</p>
                    <p className="mt-2 text-sm text-foreground">Five-screen simulation workflow behind login.</p>
                  </div>
                </div>

                <ul className="space-y-3">
                  {BENEFITS.map((benefit) => (
                    <li key={benefit} className="flex items-start gap-3 text-sm text-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-[hsl(var(--data-green))]" />
                      <span>{benefit}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="hidden h-full min-h-[280px] w-px bg-border lg:block" />
            </div>
          </section>

          <section className="surface-card p-6 sm:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-muted/60">
                {mode === "sign-up" ? <Sparkles className="h-5 w-5" /> : <LockKeyhole className="h-5 w-5" />}
              </div>
              <div>
                <p className="label-meta">Hosted access</p>
                <h2 className="text-xl font-semibold text-foreground">
                  {mode === "sign-up" ? "Create your hosted account" : "Log in to continue"}
                </h2>
              </div>
            </div>

            <div className="mb-6 grid grid-cols-2 rounded-2xl border border-border bg-muted/30 p-1" role="tablist" aria-label="Authentication mode">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "sign-up"}
                onClick={() => setMode("sign-up")}
                className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                  mode === "sign-up" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                }`}
              >
                Create account
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "log-in"}
                onClick={() => setMode("log-in")}
                className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                  mode === "log-in" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                }`}
              >
                Log in
              </button>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label htmlFor="hosted-auth-email" className="text-sm font-medium text-foreground">
                  Work email
                </label>
                <Input
                  id="hosted-auth-email"
                  autoComplete="email"
                  placeholder="team@company.com"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="hosted-auth-password" className="text-sm font-medium text-foreground">
                  Password
                </label>
                <Input
                  id="hosted-auth-password"
                  autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
                  placeholder="At least 8 characters"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>

              <div className="rounded-2xl border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
                Shared Gemini runtime is provided by the hosted server after login. Personal API keys are hidden on this
                branch.
              </div>

              {configurationError ? <p className="text-sm text-destructive">{configurationError}</p> : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              {feedback ? <p className="text-sm text-[hsl(var(--data-green))]">{feedback}</p> : null}

              <Button
                type="submit"
                className="w-full"
                disabled={submitting || !email.trim() || !password || Boolean(configurationError)}
              >
                {submitting ? "Working..." : mode === "sign-up" ? "Create account" : "Log in"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>

            <p className="mt-4 text-sm text-muted-foreground">
              Need plan context first?{" "}
              <Link to="/pricing" className="text-foreground underline underline-offset-4">
                Review the hosted pricing preview.
              </Link>
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
