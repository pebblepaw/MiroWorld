import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { StepProgress } from "@/components/StepProgress";
import { OnboardingModal } from "@/components/OnboardingModal";
import { AppProvider, useApp } from "@/contexts/AppContext";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import AgentConfig from "@/pages/AgentConfig";
import Analytics from "@/pages/Analytics";
import HostedEntry from "@/pages/HostedEntry";
import HostedPricing from "@/pages/HostedPricing";
import NotFound from "@/pages/NotFound";
import PolicyUpload from "@/pages/PolicyUpload";
import ReportChat from "@/pages/ReportChat";
import Simulation from "@/pages/Simulation";

const queryClient = new QueryClient();
const APP_STATE_STORAGE_KEY = "miroworld-app-state";

function FullScreenStatus({ description, title }: { description: string; title: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="surface-card flex max-w-md flex-col items-center gap-4 p-8 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <div className="space-y-1">
          <p className="label-meta">Hosted workspace</p>
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
    </div>
  );
}

function MainContent() {
  const { currentStep } = useApp();

  switch (currentStep) {
    case 1:
      return <PolicyUpload />;
    case 2:
      return <AgentConfig />;
    case 3:
      return <Simulation />;
    case 4:
      return <ReportChat />;
    case 5:
      return <Analytics />;
    default:
      return <PolicyUpload />;
  }
}

function HostedWorkspaceShell() {
  const { sessionId } = useApp();
  const { signOut, user } = useAuth();
  const [onboardingOpen, setOnboardingOpen] = useState(() => !sessionId);

  useEffect(() => {
    if (!sessionId) {
      setOnboardingOpen(true);
    }
  }, [sessionId]);

  async function handleSignOut() {
    try {
      window.sessionStorage.removeItem(APP_STATE_STORAGE_KEY);
    } catch {
      // Ignore storage failures during logout cleanup.
    }

    await signOut();
  }

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden bg-background">
        <AppSidebar
          onOpenSettings={() => setOnboardingOpen(true)}
          onSignOut={() => void handleSignOut()}
          userEmail={user?.email ?? null}
        />
        <div className="flex h-full flex-1 flex-col overflow-hidden">
          <header className="flex h-11 flex-shrink-0 items-center border-b border-border bg-card/50 px-2">
            <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
            <div className="flex-1">
              <StepProgress />
            </div>
          </header>
          <main className="relative flex-1 overflow-hidden">
            <MainContent />
          </main>
        </div>
        <OnboardingModal isOpen={onboardingOpen} onClose={() => setOnboardingOpen(false)} />
      </div>
    </SidebarProvider>
  );
}

function PublicHomeRoute() {
  const { isLoading, session } = useAuth();

  if (isLoading) {
    return (
      <FullScreenStatus
        title="Checking your hosted access"
        description="Restoring the Supabase session before we decide whether to show the public entry or the gated workspace."
      />
    );
  }

  if (session) {
    return <Navigate to="/app" replace />;
  }

  return <HostedEntry />;
}

function ProtectedWorkspaceRoute() {
  const { isLoading, session } = useAuth();

  if (isLoading) {
    return (
      <FullScreenStatus
        title="Loading your hosted workspace"
        description="Hang on while we restore the authenticated simulation shell."
      />
    );
  }

  if (!session) {
    return <Navigate to="/" replace />;
  }

  return (
    <AppProvider>
      <HostedWorkspaceShell />
    </AppProvider>
  );
}

const App = () => {
  const basename = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <AuthProvider>
            <BrowserRouter basename={basename}>
              <Routes>
                <Route path="/" element={<PublicHomeRoute />} />
                <Route path="/pricing" element={<HostedPricing />} />
                <Route path="/app" element={<ProtectedWorkspaceRoute />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
