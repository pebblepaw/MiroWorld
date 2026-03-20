import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { StepProgress } from "@/components/StepProgress";
import { AppProvider, useApp } from "@/contexts/AppContext";
import PolicyUpload from "@/pages/PolicyUpload";
import AgentConfig from "@/pages/AgentConfig";
import Simulation from "@/pages/Simulation";
import Analysis from "@/pages/Analysis";
import AgentChat from "@/pages/AgentChat";

const queryClient = new QueryClient();

function MainContent() {
  const { currentStep } = useApp();

  const renderStep = () => {
    switch (currentStep) {
      case 1: return <PolicyUpload />;
      case 2: return <AgentConfig />;
      case 3: return <Simulation />;
      case 4: return <Analysis />;
      case 5: return <AgentChat />;
      default: return <PolicyUpload />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <header className="h-12 flex items-center border-b border-border px-2 bg-card/30 backdrop-blur-sm flex-shrink-0">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
        <div className="flex-1">
          <StepProgress />
        </div>
      </header>
      <main className="flex-1 overflow-hidden dot-pattern relative">
        {renderStep()}
      </main>
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <AppProvider>
        <SidebarProvider>
          <div className="h-screen flex w-full overflow-hidden bg-background">
            <AppSidebar />
            <MainContent />
          </div>
        </SidebarProvider>
      </AppProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
