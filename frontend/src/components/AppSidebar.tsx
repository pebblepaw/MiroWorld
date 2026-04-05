import { useCallback, useEffect, useMemo, useState } from 'react';
import { Upload, Users, MessageSquare, BarChart3, Bot, Lock, Check, Settings2, Loader2, RefreshCcw } from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/hooks/use-toast';
import {
  ConsoleModelOption,
  ConsoleModelProvider,
  ModelProviderId,
  getModelProviderCatalog,
  getSessionModelConfig,
  listProviderModels,
  updateSessionModelConfig,
} from '@/lib/console-api';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
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
  { step: 4, title: 'Report', icon: BarChart3, path: '/report' },
  { step: 5, title: 'Analytics', icon: Bot, path: '/analytics' },
];

export function AppSidebar({ onOpenSettings }: { onOpenSettings?: () => void }) {
  const {
    currentStep,
    completedSteps,
    setCurrentStep,
    sessionId,
    country,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
  } = useApp();
  const { state } = useSidebar();
  const collapsed = state === 'collapsed';

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [providers, setProviders] = useState<ConsoleModelProvider[]>([]);
  const [providerLoading, setProviderLoading] = useState(false);
  const [modelOptions, setModelOptions] = useState<ConsoleModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [draftProvider, setDraftProvider] = useState<ModelProviderId>(modelProvider);
  const [draftModel, setDraftModel] = useState(modelName);
  const [draftEmbedModel, setDraftEmbedModel] = useState(embedModelName);
  const [draftApiKey, setDraftApiKey] = useState(modelApiKey);
  const [draftBaseUrl, setDraftBaseUrl] = useState(modelBaseUrl);

  const canAccess = (step: number) => step === 1 || completedSteps.includes(step - 1);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === draftProvider),
    [providers, draftProvider],
  );

  const loadProviders = useCallback(async () => {
    setProviderLoading(true);
    try {
      const payload = await getModelProviderCatalog();
      setProviders(payload.providers);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load model providers.';
      setSettingsError(message);
      toast({
        title: 'Could not load providers',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setProviderLoading(false);
    }
  }, []);

  const loadModels = useCallback(async (
    providerId: ModelProviderId,
    options: { apiKey?: string; baseUrl?: string; preferredModel?: string } = {},
  ) => {
    setModelsLoading(true);
    setSettingsError(null);
    try {
      const payload = await listProviderModels(providerId, {
        api_key: options.apiKey?.trim() || undefined,
        base_url: options.baseUrl?.trim() || undefined,
      });
      setModelOptions(payload.models);
      if (payload.models.length === 0) {
        return;
      }

      setDraftModel((current) => {
        const availableIds = new Set(payload.models.map((model) => model.id));
        const preferred = options.preferredModel?.trim();
        if (preferred && availableIds.has(preferred)) {
          return preferred;
        }
        if (availableIds.has(current)) {
          return current;
        }
        const providerDefault = providers.find((provider) => provider.id === providerId)?.default_model;
        if (providerDefault && availableIds.has(providerDefault)) {
          return providerDefault;
        }
        return payload.models[0].id;
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load models.';
      setModelOptions([]);
      setSettingsError(message);
    } finally {
      setModelsLoading(false);
    }
  }, [providers]);

  const syncDraftFromContext = useCallback(() => {
    setDraftProvider(modelProvider);
    setDraftModel(modelName);
    setDraftEmbedModel(embedModelName);
    setDraftApiKey(modelApiKey);
    setDraftBaseUrl(modelBaseUrl);
    setSettingsError(null);
  }, [embedModelName, modelApiKey, modelBaseUrl, modelName, modelProvider]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    syncDraftFromContext();
  }, [settingsOpen, syncDraftFromContext]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    if (providers.length > 0 || providerLoading) {
      return;
    }
    void loadProviders();
  }, [loadProviders, providerLoading, providers.length, settingsOpen]);

  useEffect(() => {
    if (!settingsOpen || !sessionId) {
      return;
    }

    let cancelled = false;
    const hydrateFromSession = async () => {
      try {
        const payload = await getSessionModelConfig(sessionId);
        if (cancelled) {
          return;
        }
        setDraftProvider(payload.model_provider);
        setDraftModel(payload.model_name);
        setDraftEmbedModel(payload.embed_model_name);
        setDraftBaseUrl(payload.base_url);
      } catch {
        // Keep local draft if backend model config cannot be fetched.
      }
    };

    void hydrateFromSession();
    return () => {
      cancelled = true;
    };
  }, [sessionId, settingsOpen]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    void loadModels(draftProvider, {
      apiKey: draftApiKey,
      baseUrl: draftBaseUrl,
      preferredModel: draftModel,
    });
  }, [draftProvider, loadModels, settingsOpen]);

  const handleProviderChange = (nextProvider: ModelProviderId) => {
    setDraftProvider(nextProvider);
    const nextProviderMeta = providers.find((provider) => provider.id === nextProvider);
    if (nextProviderMeta) {
      setDraftModel(nextProviderMeta.default_model);
      setDraftEmbedModel(nextProviderMeta.default_embed_model);
      setDraftBaseUrl(nextProviderMeta.default_base_url);
    }
    setSettingsError(null);
  };

  const handleRefreshModels = () => {
    void loadModels(draftProvider, {
      apiKey: draftApiKey,
      baseUrl: draftBaseUrl,
      preferredModel: draftModel,
    });
  };

  const handleSaveSettings = async () => {
    const resolvedModel = draftModel.trim();
    if (!resolvedModel) {
      setSettingsError('Select a model before saving.');
      return;
    }

    const resolvedApiKey = draftApiKey.trim();
    const resolvedBaseUrl = (
      draftBaseUrl.trim() ||
      selectedProvider?.default_base_url ||
      modelBaseUrl
    );
    const resolvedEmbedModel = (
      draftEmbedModel.trim() ||
      selectedProvider?.default_embed_model ||
      embedModelName
    );

    setSaving(true);
    setSettingsError(null);
    try {
      if (sessionId) {
        const payload = await updateSessionModelConfig(sessionId, {
          model_provider: draftProvider,
          model_name: resolvedModel,
          embed_model_name: resolvedEmbedModel,
          api_key: resolvedApiKey || undefined,
          base_url: resolvedBaseUrl,
        });
        setModelProvider(payload.model_provider);
        setModelName(payload.model_name);
        setEmbedModelName(payload.embed_model_name);
        setModelBaseUrl(payload.base_url);
        setModelApiKey(resolvedApiKey);
      } else {
        setModelProvider(draftProvider);
        setModelName(resolvedModel);
        setEmbedModelName(resolvedEmbedModel);
        setModelBaseUrl(resolvedBaseUrl);
        setModelApiKey(resolvedApiKey);
      }

      setSettingsOpen(false);
      toast({
        title: 'Model settings saved',
        description: sessionId
          ? 'Provider and model have been updated for this session.'
          : 'Provider and model will be applied when a new session starts.',
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save model settings.';
      setSettingsError(message);
      toast({
        title: 'Could not save settings',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Sidebar collapsible="icon" className="border-r border-border bg-sidebar">
        <SidebarHeader className="p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0 bg-white/10">
              <span className="text-white font-mono text-sm font-bold">M</span>
            </div>
            {!collapsed && (
              <div>
                <h1 className="text-foreground font-semibold text-base tracking-wide">McKAInsey</h1>
                <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-[0.2em]">Simulation Engine</p>
              </div>
            )}
          </div>
        </SidebarHeader>
        <SidebarContent className="pt-4 px-2">
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
                        onClick={() => !locked && setCurrentStep(step)}
                        className={`relative h-10 transition-colors rounded-md overflow-hidden group ${
                          active
                            ? 'bg-white/8 text-foreground'
                            : locked
                            ? 'text-muted-foreground/30 cursor-not-allowed'
                            : 'text-muted-foreground hover:text-foreground hover:bg-white/4'
                        }`}
                        disabled={locked}
                      >
                        {active && (
                          <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-white rounded-full" />
                        )}
                        <div className="relative flex items-center justify-center w-5 h-5 z-10">
                          {completed && !active ? (
                            <Check className="w-3.5 h-3.5 text-white/60" />
                          ) : locked ? (
                            <Lock className="w-3.5 h-3.5" />
                          ) : (
                            <Icon className="w-3.5 h-3.5" />
                          )}
                        </div>
                        {!collapsed && (
                          <div className="flex items-center gap-2 ml-1 z-10 relative">
                            <span className="font-mono text-[9px] opacity-40">{step}</span>
                            <span className="text-sm">{title}</span>
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
        <SidebarFooter className="p-2 border-t border-border">
          {!collapsed && (
            <div className="px-3 pb-2 pt-1 flex items-center justify-between text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              <span>
                {country === 'singapore' ? '🇸🇬' : country === 'usa' ? '🇺🇸' : '🌍'} {country} · {modelProvider}
              </span>
            </div>
          )}
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton 
                onClick={onOpenSettings} 
                tooltip="Configure Platform"
              >
                <Settings2 className="w-4 h-4 text-muted-foreground mr-2" />
                <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">Configure</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-w-md border-border bg-background/95 backdrop-blur">
          <DialogHeader>
            <DialogTitle>Model Settings</DialogTitle>
            <DialogDescription>
              Choose the provider, model, and API key used by the runtime.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="provider-select">Provider</Label>
              <Select value={draftProvider} onValueChange={(value) => handleProviderChange(value as ModelProviderId)}>
                <SelectTrigger id="provider-select" disabled={providerLoading}>
                  <SelectValue placeholder={providerLoading ? 'Loading providers...' : 'Select provider'} />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="model-select">Model</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleRefreshModels}
                  disabled={modelsLoading}
                  className="h-7 px-2"
                >
                  {modelsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCcw className="w-3.5 h-3.5" />}
                  Refresh
                </Button>
              </div>
              <Select value={draftModel} onValueChange={setDraftModel} disabled={modelsLoading || modelOptions.length === 0}>
                <SelectTrigger id="model-select">
                  <SelectValue placeholder={modelsLoading ? 'Loading models...' : 'Select model'} />
                </SelectTrigger>
                <SelectContent>
                  {modelOptions.map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {modelOptions.length === 0 && !modelsLoading && (
                <Input
                  value={draftModel}
                  onChange={(event) => setDraftModel(event.target.value)}
                  placeholder="Enter model name"
                  className="mt-2"
                />
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="api-key-input">
                API Key {selectedProvider?.requires_api_key ? '(required)' : '(optional)'}
              </Label>
              <Input
                id="api-key-input"
                type="password"
                value={draftApiKey}
                onChange={(event) => setDraftApiKey(event.target.value)}
                placeholder="Paste API key"
                autoComplete="off"
              />
            </div>

            {settingsError && <p className="text-xs text-destructive">{settingsError}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSettingsOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button type="button" onClick={handleSaveSettings} disabled={saving || !draftModel.trim()}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
