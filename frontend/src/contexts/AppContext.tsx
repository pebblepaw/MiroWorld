import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, ReactNode, SetStateAction } from 'react';
import { Agent, SimPost } from '@/data/mockData';
import {
  getBundledDemoOutput,
  isStaticDemoBootMode,
  KnowledgeArtifact,
  ModelProviderId,
  normalizeUseCaseId,
  PopulationArtifact,
  SimulationState,
} from '@/lib/console-api';

export type AnalysisQuestion = {
  question: string;
  type: 'scale' | 'yes-no' | 'open-ended';
  metric_name: string;
  metric_label?: string;
  metric_unit?: string;
  threshold?: number;
  threshold_direction?: string;
  report_title: string;
  tooltip?: string;
  /** 'preset' = from config YAML, 'custom' = user-created */
  source?: 'preset' | 'custom';
  /** metadata generation status for custom questions */
  metadataStatus?: 'pending' | 'loading' | 'ready' | 'error';
};
type ChatHistoryEntry = {
  role: 'user' | 'agent';
  content: string;
  agentId?: string;
};

interface AppState {
  currentStep: number;
  completedSteps: number[];
  sessionId: string | null;
  country: string;
  useCase: string;
  modelProvider: ModelProviderId;
  modelName: string;
  embedModelName: string;
  modelApiKey: string;
  modelBaseUrl: string;
  uploadedFiles: File[];
  analysisQuestions: AnalysisQuestion[];
  knowledgeGraphReady: boolean;
  knowledgeArtifact: KnowledgeArtifact | null;
  knowledgeLoading: boolean;
  knowledgeError: string | null;
  agentCount: number;
  sampleMode: 'affected_groups' | 'population_baseline';
  samplingInstructions: string;
  sampleSeed: number | null;
  populationArtifact: PopulationArtifact | null;
  populationLoading: boolean;
  populationError: string | null;
  agents: Agent[];
  agentsGenerated: boolean;
  simulationRounds: number;
  simulationComplete: boolean;
  simulationState: SimulationState | null;
  simPosts: SimPost[];
  chatHistory: Record<string, ChatHistoryEntry[]>;
  analysisActiveTab: string;
  simSelectedRound: number | 'all';
  simSortBy: 'new' | 'popular';
  simControversyBoostEnabled: boolean;
}

interface AppContextType extends AppState {
  setCurrentStep: (step: number) => void;
  completeStep: (step: number) => void;
  setSessionId: (sessionId: string | null) => void;
  setCountry: (country: string) => void;
  setUseCase: (useCase: string) => void;
  setModelProvider: (provider: ModelProviderId) => void;
  setModelName: (modelName: string) => void;
  setEmbedModelName: (embedModelName: string) => void;
  setModelApiKey: (modelApiKey: string) => void;
  setModelBaseUrl: (modelBaseUrl: string) => void;
  setUploadedFiles: (files: File[]) => void;
  addUploadedFile: (file: File) => void;
  removeUploadedFile: (index: number) => void;
  setAnalysisQuestions: (questions: AnalysisQuestion[]) => void;
  addAnalysisQuestion: (question: AnalysisQuestion) => void;
  updateAnalysisQuestion: (index: number, question: AnalysisQuestion) => void;
  removeAnalysisQuestion: (index: number) => void;
  setKnowledgeGraphReady: (ready: boolean) => void;
  setKnowledgeArtifact: (artifact: KnowledgeArtifact | null) => void;
  setKnowledgeLoading: (loading: boolean) => void;
  setKnowledgeError: (error: string | null) => void;
  setAgentCount: (count: number) => void;
  setSampleMode: (mode: 'affected_groups' | 'population_baseline') => void;
  setSamplingInstructions: (value: string) => void;
  setSampleSeed: (seed: number | null) => void;
  setPopulationArtifact: (artifact: PopulationArtifact | null) => void;
  setPopulationLoading: (loading: boolean) => void;
  setPopulationError: (error: string | null) => void;
  setAgents: (agents: Agent[]) => void;
  setAgentsGenerated: (gen: boolean) => void;
  setSimulationRounds: (rounds: number) => void;
  setSimulationComplete: (complete: boolean) => void;
  setSimulationState: React.Dispatch<SetStateAction<SimulationState | null>>;
  setSimPosts: (posts: SimPost[]) => void;
  addChatMessage: (threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => void;
  setAnalysisActiveTab: (tab: string) => void;
  setSimSelectedRound: (round: number | 'all') => void;
  setSimSortBy: (sortBy: 'new' | 'popular') => void;
  setSimControversyBoostEnabled: (enabled: boolean) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const DEFAULT_APP_STATE: AppState = {
  currentStep: 1,
  completedSteps: [],
  sessionId: null,
  country: 'singapore',
  useCase: 'public-policy-testing',
  modelProvider: 'ollama',
  modelName: 'qwen3:4b-instruct-2507-q4_K_M',
  embedModelName: 'nomic-embed-text',
  modelApiKey: '',
  modelBaseUrl: 'http://127.0.0.1:11434/v1/',
  uploadedFiles: [],
  analysisQuestions: [],
  knowledgeGraphReady: false,
  knowledgeArtifact: null,
  knowledgeLoading: false,
  knowledgeError: null,
  agentCount: 0,
  sampleMode: 'affected_groups',
  samplingInstructions: '',
  sampleSeed: null,
  populationArtifact: null,
  populationLoading: false,
  populationError: null,
  agents: [],
  agentsGenerated: false,
  simulationRounds: 3,
  simulationComplete: false,
  simulationState: null,
  simPosts: [],
  chatHistory: {},
  analysisActiveTab: 'report',
  simSelectedRound: 'all',
  simSortBy: 'new',
  simControversyBoostEnabled: false,
};

const SESSION_STORAGE_KEY = 'miroworld-app-state';
const STATIC_DEMO_BUNDLE_KEY_STORAGE = 'miroworld-demo-static-bundle-key';
const STATIC_DEMO_SESSION_CACHE_PREFIXES = ['miroworld-report-', 'miroworld-analytics-'];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function clearStaticDemoSessionCaches(): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const keysToRemove: string[] = [];
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const key = window.sessionStorage.key(index);
      if (!key) {
        continue;
      }
      if (STATIC_DEMO_SESSION_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
        keysToRemove.push(key);
      }
    }
    for (const key of keysToRemove) {
      window.sessionStorage.removeItem(key);
    }
  } catch {
    // Ignore storage access failures.
  }
}

function normalizeCountryId(country: string): string {
  const normalized = String(country || '').trim().toLowerCase();
  if (normalized === 'sg') return 'singapore';
  if (normalized === 'us') return 'usa';
  return normalized || 'singapore';
}

function formatLabel(raw: string): string {
  return raw
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function resolveDemoGeography(persona: Record<string, unknown>, country: string): string {
  const normalizedCountry = normalizeCountryId(country);
  const preferredKeys = normalizedCountry === 'usa'
    ? ['state', 'geography', 'planning_area', 'location', 'region', 'area']
    : ['planning_area', 'geography', 'state', 'location', 'region', 'area'];
  for (const key of preferredKeys) {
    const value = String(persona[key] ?? '').trim();
    if (value) {
      return value;
    }
  }
  return 'Unknown';
}

function resolveDemoDisplayName(row: Record<string, unknown>): string {
  const direct = String(row.display_name ?? '').trim();
  if (direct) return direct;
  const persona = asRecord(row.persona);
  const personaName = String(persona.display_name ?? persona.name ?? '').trim();
  if (personaName) return personaName;
  return formatLabel(String(persona.occupation ?? row.agent_id ?? 'Resident'));
}

function normalizeAnalysisQuestions(value: unknown): AnalysisQuestion[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item, index) => {
    const entry = asRecord(item);
    const question = String(entry.question ?? '').trim();
    const type = entry.type === 'yes-no' || entry.type === 'open-ended' ? entry.type : 'scale';
    return {
      question,
      type,
      metric_name: String(entry.metric_name ?? entry.metricName ?? `demo_metric_${index + 1}`),
      metric_label: entry.metric_label ? String(entry.metric_label) : undefined,
      metric_unit: entry.metric_unit ? String(entry.metric_unit) : undefined,
      threshold: typeof entry.threshold === 'number' ? entry.threshold : undefined,
      threshold_direction: entry.threshold_direction ? String(entry.threshold_direction) : undefined,
      report_title: String(entry.report_title ?? question ?? `Question ${index + 1}`),
      tooltip: entry.tooltip ? String(entry.tooltip) : undefined,
      source: (entry.source as AnalysisQuestion['source']) ?? 'preset',
      metadataStatus: 'ready',
    };
  });
}

function demoPopulationToArtifact(value: Record<string, unknown>, sessionId: string): PopulationArtifact | null {
  const sampledPersonas = Array.isArray(value.sampled_personas) ? (value.sampled_personas as PopulationArtifact['sampled_personas']) : [];
  if (sampledPersonas.length === 0 && !Number(value.sample_count ?? 0)) {
    return null;
  }
  return {
    session_id: String(value.session_id ?? sessionId),
    candidate_count: Number(value.candidate_count ?? sampledPersonas.length),
    sample_count: Number(value.sample_count ?? sampledPersonas.length),
    sample_mode: (value.sample_mode as PopulationArtifact['sample_mode']) ?? 'affected_groups',
    sample_seed: Number(value.sample_seed ?? 0),
    parsed_sampling_instructions: (value.parsed_sampling_instructions as PopulationArtifact['parsed_sampling_instructions']) ?? {
      hard_filters: {},
      soft_boosts: {},
      soft_penalties: {},
      exclusions: {},
      distribution_targets: {},
      notes_for_ui: [],
    },
    coverage: (value.coverage as PopulationArtifact['coverage']) ?? {
      planning_areas: [],
      age_buckets: {},
    },
    sampled_personas: sampledPersonas,
    agent_graph: (value.agent_graph as PopulationArtifact['agent_graph']) ?? { nodes: [], links: [] },
    representativeness: (value.representativeness as PopulationArtifact['representativeness']) ?? { status: 'unknown' },
    selection_diagnostics: (value.selection_diagnostics as PopulationArtifact['selection_diagnostics']) ?? {},
  };
}

function demoPersonaToAgent(row: Record<string, unknown>, country: string): Agent {
  const persona = asRecord(row.persona);
  const selectionReason = asRecord(row.selection_reason);
  const score = Number(selectionReason.score ?? 0.5);
  const approvalScore = Math.round(Math.max(0, Math.min(1, score)) * 100);
  return {
    id: String(row.agent_id ?? `demo-agent-${Math.random()}`),
    name: resolveDemoDisplayName(row),
    age: Number(persona.age ?? 0),
    gender: String(persona.sex ?? persona.gender ?? 'Unknown'),
    ethnicity: String(persona.ethnicity ?? persona.cultural_background ?? persona.country ?? 'Unknown'),
    occupation: formatLabel(String(persona.occupation ?? 'Resident')),
    planningArea: formatLabel(resolveDemoGeography(persona, country)),
    incomeBracket: String(persona.income_bracket ?? persona.salary ?? persona.household_income ?? 'Not specified'),
    housingType: String(persona.housing_type ?? 'Not specified'),
    sentiment: approvalScore >= 67 ? 'positive' : approvalScore >= 40 ? 'neutral' : 'negative',
    approvalScore,
  };
}

function demoSimulationState(value: Record<string, unknown>, sessionId: string): SimulationState | null {
  if (Object.keys(value).length === 0) {
    return null;
  }
  return {
    session_id: String(value.session_id ?? sessionId),
    status: String(value.status ?? 'completed'),
    event_count: Number(value.event_count ?? 0),
    last_round: Number(value.last_round ?? 0),
    platform: (value.platform as string | null | undefined) ?? 'reddit',
    planned_rounds: Number(value.planned_rounds ?? 0),
    current_round: Number(value.current_round ?? value.last_round ?? 0),
    elapsed_seconds: Number(value.elapsed_seconds ?? 0),
    estimated_total_seconds: Number(value.estimated_total_seconds ?? value.elapsed_seconds ?? 0),
    estimated_remaining_seconds: Number(value.estimated_remaining_seconds ?? 0),
    counters: (value.counters as SimulationState['counters']) ?? { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
    checkpoint_status: (value.checkpoint_status as SimulationState['checkpoint_status']) ?? {},
    top_threads: Array.isArray(value.top_threads) ? (value.top_threads as Array<Record<string, unknown>>) : [],
    discussion_momentum: (value.discussion_momentum as Record<string, unknown>) ?? {},
    latest_metrics: (value.latest_metrics as Record<string, unknown>) ?? {},
    recent_events: Array.isArray(value.recent_events) ? (value.recent_events as Array<Record<string, unknown>>) : [],
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<AppState>;
        return { ...DEFAULT_APP_STATE, ...parsed };
      }
    } catch {
      // Ignore parse errors (corrupted storage)
    }
    return DEFAULT_APP_STATE;
  });
  const staticDemoHydratedRef = useRef(false);

  useEffect(() => {
    if (!isStaticDemoBootMode() || staticDemoHydratedRef.current) {
      return;
    }

    let cancelled = false;
    staticDemoHydratedRef.current = true;

    void getBundledDemoOutput().then((rawDemo) => {
      if (cancelled) {
        return;
      }

      const demo = asRecord(rawDemo);
      const session = asRecord(demo.session);
      const sourceRun = asRecord(demo.source_run);
      const population = asRecord(demo.population);
      const simulation = asRecord(demo.simulationState);
      const demoSessionId = String(session.session_id ?? simulation.session_id ?? '').trim();
      const demoCountry = normalizeCountryId(String(sourceRun.country ?? 'singapore'));
      const demoUseCase = normalizeUseCaseId(String(sourceRun.use_case ?? 'public-policy-testing'));
      const demoRounds = Number(sourceRun.rounds ?? simulation.planned_rounds ?? 0);
      const demoQuestions = normalizeAnalysisQuestions(demo.analysis_questions ?? sourceRun.analysis_questions);
      const demoPopulation = demoPopulationToArtifact(population, demoSessionId);
      const demoAgents = demoPopulation?.sampled_personas.map((row) => demoPersonaToAgent(asRecord(row), demoCountry)) ?? [];
      const demoState = demoSimulationState(simulation, demoSessionId);
      const demoBundleKey = demoSessionId || [demoCountry, demoUseCase, demoModel].filter(Boolean).join('|');

      let bundleChanged = false;
      if (demoBundleKey) {
        try {
          const persistedBundleKey = window.sessionStorage.getItem(STATIC_DEMO_BUNDLE_KEY_STORAGE);
          bundleChanged = persistedBundleKey !== demoBundleKey;
          if (bundleChanged) {
            clearStaticDemoSessionCaches();
          }
          window.sessionStorage.setItem(STATIC_DEMO_BUNDLE_KEY_STORAGE, demoBundleKey);
        } catch {
          bundleChanged = false;
        }
      }

      setState((previous) => {
        const next = bundleChanged ? { ...DEFAULT_APP_STATE } : { ...previous };

        if (demoSessionId) {
          next.sessionId = demoSessionId;
        }
        if (demoCountry) {
          next.country = demoCountry;
        }
        if (demoUseCase) {
          next.useCase = demoUseCase;
        }
        if (demoQuestions.length > 0) {
          next.analysisQuestions = demoQuestions;
        }
        if (demoPopulation) {
          next.populationArtifact = demoPopulation;
          next.agentCount = demoPopulation.sample_count;
          next.sampleSeed = demoPopulation.sample_seed;
        }
        if (demoAgents.length > 0) {
          next.agents = demoAgents;
          next.agentsGenerated = true;
        }
        if (demoRounds > 0) {
          next.simulationRounds = demoRounds;
        }
        if (demoState) {
          next.simulationState = demoState;
          next.simulationComplete = demoState.status === 'completed';
        }

        return next;
      });
    }).catch(() => {
      staticDemoHydratedRef.current = false;
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const persisted = {
      sessionId: state.sessionId,
      currentStep: state.currentStep,
      completedSteps: state.completedSteps,
      country: state.country,
      useCase: state.useCase,
      modelProvider: state.modelProvider,
      modelName: state.modelName,
      embedModelName: state.embedModelName,
      modelApiKey: state.modelApiKey,
      modelBaseUrl: state.modelBaseUrl,
      analysisQuestions: state.analysisQuestions,
      knowledgeGraphReady: state.knowledgeGraphReady,
      agentCount: state.agentCount,
      sampleMode: state.sampleMode,
      samplingInstructions: state.samplingInstructions,
      sampleSeed: state.sampleSeed,
      agentsGenerated: state.agentsGenerated,
      simulationRounds: state.simulationRounds,
      simulationComplete: state.simulationComplete,
      simulationState: state.simulationState,
      analysisActiveTab: state.analysisActiveTab,
      simSelectedRound: state.simSelectedRound,
      simSortBy: state.simSortBy,
      simControversyBoostEnabled: state.simControversyBoostEnabled,
    };
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(persisted));
    } catch {
      // Ignore storage errors (e.g., private browsing quota)
    }
  }, [state]);

  const setCurrentStep = useCallback((step: number) => setState(s => ({ ...s, currentStep: step })), []);
  const completeStep = useCallback((step: number) => setState(s => ({
    ...s,
    completedSteps: s.completedSteps.includes(step) ? s.completedSteps : [...s.completedSteps, step],
  })), []);
  const setSessionId = useCallback((sessionId: string | null) => setState(s => {
    if (s.sessionId === sessionId) {
      return s;
    }
    const switchingExistingSessions = s.sessionId !== null && sessionId !== null;
    if (!switchingExistingSessions) {
      return {
        ...s,
        sessionId,
      };
    }
    return {
      ...s,
      sessionId,
      uploadedFiles: [],
      analysisQuestions: [],
      knowledgeGraphReady: false,
      knowledgeArtifact: null,
      knowledgeLoading: false,
      knowledgeError: null,
      agentCount: 0,
      sampleMode: 'affected_groups',
      samplingInstructions: '',
      sampleSeed: null,
      populationArtifact: null,
      populationLoading: false,
      populationError: null,
      agents: [],
      agentsGenerated: false,
      simulationRounds: 3,
      simulationComplete: false,
      simulationState: null,
      simPosts: [],
      chatHistory: {},
    };
  }), []);
  const setCountry = useCallback((country: string) => setState(s => ({ ...s, country })), []);
  const setUseCase = useCallback((useCase: string) => setState(s => ({ ...s, useCase })), []);
  const setModelProvider = useCallback((modelProvider: ModelProviderId) => setState(s => ({ ...s, modelProvider })), []);
  const setModelName = useCallback((modelName: string) => setState(s => ({ ...s, modelName })), []);
  const setEmbedModelName = useCallback((embedModelName: string) => setState(s => ({ ...s, embedModelName })), []);
  const setModelApiKey = useCallback((modelApiKey: string) => setState(s => ({ ...s, modelApiKey })), []);
  const setModelBaseUrl = useCallback((modelBaseUrl: string) => setState(s => ({ ...s, modelBaseUrl })), []);
  const setUploadedFiles = useCallback((files: File[]) => setState(s => ({ ...s, uploadedFiles: files })), []);
  const addUploadedFile = useCallback((file: File) => setState(s => ({ ...s, uploadedFiles: [...s.uploadedFiles, file] })), []);
  const removeUploadedFile = useCallback((index: number) => setState(s => ({ ...s, uploadedFiles: s.uploadedFiles.filter((_, i) => i !== index) })), []);
  const setAnalysisQuestions = useCallback((questions: AnalysisQuestion[]) => setState(s => ({ ...s, analysisQuestions: questions })), []);
  const addAnalysisQuestion = useCallback((question: AnalysisQuestion) => setState(s => ({ ...s, analysisQuestions: [...s.analysisQuestions, question] })), []);
  const updateAnalysisQuestion = useCallback((index: number, question: AnalysisQuestion) => setState(s => ({
    ...s,
    analysisQuestions: s.analysisQuestions.map((q, i) => i === index ? question : q),
  })), []);
  const removeAnalysisQuestion = useCallback((index: number) => setState(s => ({
    ...s,
    analysisQuestions: s.analysisQuestions.filter((_, i) => i !== index),
  })), []);
  const setKnowledgeGraphReady = useCallback((ready: boolean) => setState(s => ({ ...s, knowledgeGraphReady: ready })), []);
  const setKnowledgeArtifact = useCallback((knowledgeArtifact: KnowledgeArtifact | null) => setState(s => ({ ...s, knowledgeArtifact })), []);
  const setKnowledgeLoading = useCallback((knowledgeLoading: boolean) => setState(s => ({ ...s, knowledgeLoading })), []);
  const setKnowledgeError = useCallback((knowledgeError: string | null) => setState(s => ({ ...s, knowledgeError })), []);
  const setAgentCount = useCallback((count: number) => setState(s => ({ ...s, agentCount: count })), []);
  const setSampleMode = useCallback((sampleMode: 'affected_groups' | 'population_baseline') => setState(s => ({ ...s, sampleMode })), []);
  const setSamplingInstructions = useCallback((samplingInstructions: string) => setState(s => ({ ...s, samplingInstructions })), []);
  const setSampleSeed = useCallback((sampleSeed: number | null) => setState(s => ({ ...s, sampleSeed })), []);
  const setPopulationArtifact = useCallback((populationArtifact: PopulationArtifact | null) => setState(s => ({ ...s, populationArtifact })), []);
  const setPopulationLoading = useCallback((populationLoading: boolean) => setState(s => ({ ...s, populationLoading })), []);
  const setPopulationError = useCallback((populationError: string | null) => setState(s => ({ ...s, populationError })), []);
  const setAgents = useCallback((agents: Agent[]) => setState(s => ({ ...s, agents })), []);
  const setAgentsGenerated = useCallback((gen: boolean) => setState(s => ({ ...s, agentsGenerated: gen })), []);
  const setSimulationRounds = useCallback((rounds: number) => setState(s => ({ ...s, simulationRounds: rounds })), []);
  const setSimulationComplete = useCallback((complete: boolean) => setState(s => ({ ...s, simulationComplete: complete })), []);
  const setSimulationState = useCallback((simulationState: SetStateAction<SimulationState | null>) => setState(s => ({
    ...s,
    simulationState: typeof simulationState === 'function'
      ? simulationState(s.simulationState)
      : simulationState,
  })), []);
  const setSimPosts = useCallback((posts: SimPost[]) => setState(s => ({ ...s, simPosts: posts })), []);
  const setAnalysisActiveTab = useCallback((analysisActiveTab: string) => setState(s => ({ ...s, analysisActiveTab })), []);
  const setSimSelectedRound = useCallback((simSelectedRound: number | 'all') => setState(s => ({ ...s, simSelectedRound })), []);
  const setSimSortBy = useCallback((simSortBy: 'new' | 'popular') => setState(s => ({ ...s, simSortBy })), []);
  const setSimControversyBoostEnabled = useCallback((simControversyBoostEnabled: boolean) => setState(s => ({ ...s, simControversyBoostEnabled })), []);
  const addChatMessage = useCallback((threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => {
    setState(s => ({
      ...s,
      chatHistory: {
        ...s.chatHistory,
        [threadId]: [...(s.chatHistory[threadId] || []), { role, content, agentId: sourceAgentId }],
      },
    }));
  }, []);

  const value = useMemo(() => ({
    ...state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setCountry,
    setUseCase,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setAnalysisQuestions,
    addAnalysisQuestion,
    updateAnalysisQuestion,
    removeAnalysisQuestion,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimulationState,
    setSimPosts,
    addChatMessage,
    setAnalysisActiveTab,
    setSimSelectedRound,
    setSimSortBy,
    setSimControversyBoostEnabled,
  }), [
    state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setAnalysisQuestions,
    addAnalysisQuestion,
    updateAnalysisQuestion,
    removeAnalysisQuestion,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimulationState,
    setSimPosts,
    addChatMessage,
    setAnalysisActiveTab,
    setSimSelectedRound,
    setSimSortBy,
    setSimControversyBoostEnabled,
  ]);

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
