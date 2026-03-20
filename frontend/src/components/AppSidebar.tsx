import { Upload, Users, MessageSquare, BarChart3, Bot, Lock, Check } from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  useSidebar,
} from '@/components/ui/sidebar';

const steps = [
  { step: 1, title: 'Policy Upload', icon: Upload, path: '/upload' },
  { step: 2, title: 'Agent Config', icon: Users, path: '/agents' },
  { step: 3, title: 'Simulation', icon: MessageSquare, path: '/simulation' },
  { step: 4, title: 'Analysis', icon: BarChart3, path: '/analysis' },
  { step: 5, title: 'Agent Chat', icon: Bot, path: '/chat' },
];

export function AppSidebar() {
  const { currentStep, completedSteps, setCurrentStep } = useApp();
  const { state } = useSidebar();
  const collapsed = state === 'collapsed';

  const canAccess = (step: number) => step === 1 || completedSteps.includes(step - 1);

  return (
    <Sidebar collapsible="icon" className="border-r border-border bg-sidebar">
      <SidebarHeader className="p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
            <span className="text-primary font-bold text-sm">S</span>
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-foreground font-bold text-lg tracking-wider glow-text bg-clip-text text-transparent bg-gradient-to-r from-primary to-orange-300">McKAInsey</h1>
              <p className="text-muted-foreground text-[10px] leading-tight">Policy Sentiment Engine</p>
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent className="pt-4 px-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {steps.map(({ step, title, icon: Icon }) => {
                const active = currentStep === step;
                const completed = completedSteps.includes(step);
                const locked = !canAccess(step);

                return (
                  <SidebarMenuItem key={step}>
                    <SidebarMenuButton
                      onClick={() => !locked && setCurrentStep(step)}
                      className={`relative h-12 transition-all duration-300 rounded-xl overflow-hidden group ${
                        active
                          ? 'bg-gradient-to-r from-primary/20 to-transparent text-primary border border-primary/30 shadow-[0_0_15px_rgba(255,100,0,0.15)]'
                          : locked
                          ? 'text-muted-foreground/40 cursor-not-allowed'
                          : 'text-muted-foreground hover:text-foreground hover:bg-white/5 hover:border-white/10 border border-transparent'
                      }`}
                      disabled={locked}
                    >
                      {active && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-primary to-primary/50 shadow-[0_0_10px_rgba(255,100,0,0.5)]" />
                      )}
                      {!locked && !active && (
                        <div className="absolute inset-0 bg-gradient-to-r from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                      )}
                      <div className="relative flex items-center justify-center w-5 h-5 z-10">
                        {completed && !active ? (
                          <Check className="w-4 h-4 text-success" />
                        ) : locked ? (
                          <Lock className="w-4 h-4" />
                        ) : (
                          <Icon className={`w-4 h-4 transition-transform duration-300 ${active ? 'scale-110' : 'group-hover:scale-110'}`} />
                        )}
                      </div>
                      {!collapsed && (
                        <div className="flex items-center gap-2 ml-1 z-10 relative">
                          <span className="font-mono text-[10px] opacity-70">{step}/5</span>
                          <span className="text-sm font-medium">{title}</span>
                        </div>
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
