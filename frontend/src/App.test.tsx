import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

const authState = {
  isLoading: false,
  session: null as null | { access_token: string },
  user: null as null | { id: string; email?: string | null },
  signInWithPassword: vi.fn(),
  signUpWithPassword: vi.fn(),
  signOut: vi.fn(),
};

vi.mock("@/contexts/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => authState,
}));

vi.mock("@/components/StepProgress", () => ({
  StepProgress: () => <div>Step Progress</div>,
}));

vi.mock("@/pages/PolicyUpload", () => ({
  default: () => <div>Policy Upload Screen</div>,
}));

vi.mock("@/pages/AgentConfig", () => ({
  default: () => <div>Agent Config Screen</div>,
}));

vi.mock("@/pages/Simulation", () => ({
  default: () => <div>Simulation Screen</div>,
}));

vi.mock("@/pages/ReportChat", () => ({
  default: () => <div>Report Screen</div>,
}));

vi.mock("@/pages/Analytics", () => ({
  default: () => <div>Analytics Screen</div>,
}));

vi.mock("@/components/OnboardingModal", () => ({
  OnboardingModal: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div>Hosted Onboarding</div> : null),
}));

describe("Hosted app entry flow", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
    authState.isLoading = false;
    authState.session = null;
    authState.user = null;
    authState.signInWithPassword.mockReset();
    authState.signUpWithPassword.mockReset();
    authState.signOut.mockReset();
    authState.signUpWithPassword.mockResolvedValue({ session: null });
    authState.signInWithPassword.mockResolvedValue({ session: { access_token: "session-token" } });
    authState.signOut.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the public auth entry and submits sign up and log in actions while signed out", async () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: "founder@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "correct horse battery staple" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() =>
      expect(authState.signUpWithPassword).toHaveBeenCalledWith({
        email: "founder@example.com",
        password: "correct horse battery staple",
      }),
    );

    fireEvent.click(screen.getByRole("tab", { name: /log in/i }));
    fireEvent.click(await screen.findByRole("button", { name: /^log in$/i }));
    await waitFor(() =>
      expect(authState.signInWithPassword).toHaveBeenCalledWith({
        email: "founder@example.com",
        password: "correct horse battery staple",
      }),
    );

    expect(screen.queryByText("Hosted Onboarding")).not.toBeInTheDocument();
  });

  it("renders the public pricing page with starter, pro, and team plans", () => {
    window.history.pushState({}, "", "/pricing");

    render(<App />);

    expect(screen.getByRole("heading", { name: "Starter", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Team", level: 2 })).toBeInTheDocument();
    expect(screen.getAllByText(/informational preview/i).length).toBeGreaterThan(0);
  });

  it("renders the gated workspace and exposes log out while signed in", () => {
    authState.session = { access_token: "session-token" };
    authState.user = { id: "user-1", email: "founder@example.com" };

    render(<App />);

    expect(screen.getByText("Policy Upload Screen")).toBeInTheDocument();
    expect(screen.getByText("Hosted Onboarding")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(authState.signOut).toHaveBeenCalledTimes(1);
  });
});
