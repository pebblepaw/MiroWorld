import { ArrowLeft, ArrowRight, Check, Minus } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

const PLANS = [
  {
    name: "Starter",
    price: "$49",
    audience: "Solo operator or early pilot",
    features: [
      "1 hosted workspace",
      "Shared Gemini runtime",
      "Core five-screen simulation flow",
      "Email support",
    ],
    limitations: ["No SSO", "No billing automation yet"],
  },
  {
    name: "Pro",
    price: "$199",
    audience: "Small product or policy team",
    features: [
      "5 hosted seats",
      "Priority queueing",
      "Saved simulation sessions",
      "Shared workspace history",
    ],
    limitations: ["No annual discounts in MVP"],
    highlighted: true,
  },
  {
    name: "Team",
    price: "$499",
    audience: "Cross-functional hosted rollout",
    features: [
      "15 hosted seats",
      "Team-level reporting access",
      "Shared runtime defaults",
      "Dedicated onboarding support",
    ],
    limitations: ["Contracting handled offline"],
  },
];

export default function HostedPricing() {
  return (
    <div className="min-h-screen bg-background px-6 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="label-meta">Hosted pricing preview</p>
            <h1 className="text-page-title">Starter, Pro, and Team</h1>
          </div>
          <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Back to auth
          </Link>
        </header>

        <section className="surface-card p-8 sm:p-10">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <p className="label-meta">Informational preview only</p>
              <h2 className="max-w-3xl text-4xl font-semibold tracking-tight text-foreground">
                Hosted pricing is visible on this branch, but billing is not wired into the MVP.
              </h2>
              <p className="max-w-2xl text-base text-muted-foreground">
                These plans are placeholders for packaging conversations. There is no checkout flow, no Stripe logic, and
                no purchase path in this implementation.
              </p>
            </div>
            <Button asChild className="w-full sm:w-auto">
              <Link to="/">
                Return to sign up
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </section>

        <main className="grid gap-4 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <article
              key={plan.name}
              className={`surface-card flex h-full flex-col p-6 ${
                plan.highlighted ? "border-primary shadow-[0_18px_60px_-32px_hsl(var(--primary)/0.4)]" : ""
              }`}
            >
              <div className="space-y-3">
                <p className="label-meta">{plan.highlighted ? "Recommended" : "Hosted plan"}</p>
                <h2 className="text-2xl font-semibold text-foreground">{plan.name}</h2>
                <p className="text-4xl font-semibold tracking-tight text-foreground">
                  {plan.price}
                  <span className="ml-2 text-sm font-normal text-muted-foreground">/ month</span>
                </p>
                <p className="text-sm text-muted-foreground">{plan.audience}</p>
              </div>

              <div className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <div key={feature} className="flex items-start gap-3 text-sm text-foreground">
                    <Check className="mt-0.5 h-4 w-4 text-[hsl(var(--data-green))]" />
                    <span>{feature}</span>
                  </div>
                ))}
                {plan.limitations.map((limitation) => (
                  <div key={limitation} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <Minus className="mt-0.5 h-4 w-4" />
                    <span>{limitation}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
                Informational preview only. Billing is handled outside this frontend.
              </div>
            </article>
          ))}
        </main>
      </div>
    </div>
  );
}
