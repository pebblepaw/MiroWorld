import { BarChart3, Bot, Check, LogOut, MessageSquare, Settings2, Sun, Moon, Upload, Users } from "lucide-react";

import { useApp } from "@/contexts/AppContext";
import { useTheme } from "@/contexts/ThemeContext";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const BASE_URL = import.meta.env.BASE_URL.endsWith("/")
  ? import.meta.env.BASE_URL
  : `${import.meta.env.BASE_URL}/`;

const withBase = (path: string) => `${BASE_URL}${path.replace(/^\//, "")}`;

const steps = [
  { step: 1, title: "Policy Upload", icon: Upload },
  { step: 2, title: "Agent Config", icon: Users },
  { step: 3, title: "Simulation", icon: MessageSquare },
  { step: 4, title: "Report", icon: BarChart3 },
  { step: 5, title: "Analytics", icon: Bot },
];

function ThemeToggleButton() {
  const { theme, toggleTheme } = useTheme();

  return (
    <SidebarMenuButton onClick={toggleTheme} tooltip={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}>
      {theme === "dark" ? (
        <Sun className="mr-2 h-4 w-4 text-muted-foreground" />
      ) : (
        <Moon className="mr-2 h-4 w-4 text-muted-foreground" />
      )}
      <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
        {theme === "dark" ? "Light Mode" : "Dark Mode"}
      </span>
    </SidebarMenuButton>
  );
}

type AppSidebarProps = {
  onOpenSettings?: () => void;
  onSignOut?: () => void;
  userEmail?: string | null;
};

export function AppSidebar({ onOpenSettings, onSignOut, userEmail }: AppSidebarProps) {
  const { currentStep, completedSteps, country, setCurrentStep } = useApp();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  const canAccess = (step: number) => step === 1 || completedSteps.includes(step - 1);
  const countryLabel = country === "usa" ? "USA" : country === "singapore" ? "Singapore" : "Hosted";
  const countryEmoji = country === "usa" ? "🇺🇸" : country === "singapore" ? "🇸🇬" : "🌍";

  return (
    <Sidebar collapsible="icon" className="border-r border-border bg-sidebar">
      <SidebarHeader className="border-b border-border p-4">
        <div className="flex items-center gap-3">
          <img src={withBase("/logo.png")} alt="MiroWorld" className="h-8 w-8 rounded object-contain" />
          {!collapsed ? (
            <div>
              <h1 className="text-base font-semibold tracking-wide text-foreground">MiroWorld</h1>
              <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Hosted Runtime</p>
            </div>
          ) : null}
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2 pt-4">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {steps.map(({ step, title, icon: Icon }) => {
                const active = currentStep === step;
                const completed = completedSteps.includes(step);
                const locked = !canAccess(step);

                return (
                  <SidebarMenuItem key={step}>
                    <SidebarMenuButton
                      onClick={() => {
                        if (!locked) {
                          setCurrentStep(step);
                        }
                      }}
                      className={`relative h-10 overflow-hidden rounded-md text-sm transition-colors ${
                        active
                          ? "bg-foreground/[0.08] text-foreground"
                          : locked
                            ? "cursor-not-allowed text-muted-foreground/72"
                            : "text-muted-foreground/65 hover:bg-foreground/[0.04] hover:text-foreground"
                      }`}
                      disabled={locked}
                    >
                      {active ? <div className="absolute bottom-1.5 left-0 top-1.5 w-0.5 rounded-full bg-foreground" /> : null}
                      <div className="relative z-10 flex h-5 w-5 items-center justify-center">
                        {completed && !active ? (
                          <Check className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <Icon className="h-3.5 w-3.5" />
                        )}
                      </div>
                      {!collapsed ? (
                        <div className="relative z-10 ml-1 flex items-center gap-2">
                          <span className="font-mono text-[9px] opacity-55">{step}</span>
                          <span>{title}</span>
                        </div>
                      ) : null}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-border p-2">
        {!collapsed ? (
          <div className="flex flex-col gap-1 px-3 pb-2 pt-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <span>
              {countryEmoji} {countryLabel} · shared Gemini
            </span>
            {userEmail ? <span className="truncate normal-case tracking-normal">{userEmail}</span> : null}
          </div>
        ) : null}

        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={onOpenSettings} tooltip="Configure Simulation">
              <Settings2 className="mr-2 h-4 w-4 text-muted-foreground" />
              <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Configure</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={onSignOut} tooltip="Log Out">
              <LogOut className="mr-2 h-4 w-4 text-muted-foreground" />
              <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <ThemeToggleButton />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
