import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { StepProgress } from "@/components/StepProgress";
import { AppProvider, useApp } from "@/contexts/AppContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import PolicyUpload from "@/pages/PolicyUpload";
import AgentConfig from "@/pages/AgentConfig";
import Simulation from "@/pages/Simulation";
import ReportChat from "@/pages/ReportChat";
import Analytics from "@/pages/Analytics";
import { OnboardingModal } from "@/components/OnboardingModal";
import { useState, useEffect } from "react";
import { isStaticDemoBootMode } from "@/lib/console-api";

const queryClient = new QueryClient();
const APP_STATE_STORAGE_KEY = "miroworld-app-state";

function shouldResumeDemoStaticSession(): boolean {
  if (typeof window === "undefined" || !isStaticDemoBootMode()) {
    return false;
  }

  try {
    const raw = window.sessionStorage.getItem(APP_STATE_STORAGE_KEY);
    if (!raw) {
      return false;
    }

    const parsed = JSON.parse(raw) as {
      sessionId?: unknown;
      currentStep?: unknown;
      completedSteps?: unknown;
    };
    const sessionId = String(parsed.sessionId ?? "").trim();
    const currentStep = Number(parsed.currentStep ?? 1);
    const completedSteps = Array.isArray(parsed.completedSteps) ? parsed.completedSteps : [];
    return Boolean(sessionId || currentStep > 1 || completedSteps.length > 0);
  } catch {
    return false;
  }
}

function MainContent() {
  const { currentStep } = useApp();

  const renderStep = () => {
    switch (currentStep) {
      case 1: return <PolicyUpload />;
      case 2: return <AgentConfig />;
      case 3: return <Simulation />;
      case 4: return <ReportChat />;
      case 5: return <Analytics />;
      default: return <PolicyUpload />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <header className="h-11 flex items-center border-b border-border px-2 bg-card/50 flex-shrink-0">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
        <div className="flex-1">
          <StepProgress />
        </div>
      </header>
      <main className="flex-1 overflow-hidden relative">
        {renderStep()}
      </main>
    </div>
  );
}

const App = () => {
  const [onboardingOpen, setOnboardingOpen] = useState(() => !shouldResumeDemoStaticSession());

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
        <Toaster />
        <Sonner />
        <AppProvider>
          <SidebarProvider>
            <div className="h-screen flex w-full overflow-hidden bg-background">
              <AppSidebar onOpenSettings={() => setOnboardingOpen(true)} />
              <MainContent />
              <OnboardingModal isOpen={onboardingOpen} onClose={() => setOnboardingOpen(false)} />
            </div>
          </SidebarProvider>
        </AppProvider>
      </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
