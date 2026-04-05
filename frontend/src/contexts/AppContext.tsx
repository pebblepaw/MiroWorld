import React, { createContext, useCallback, useContext, useMemo, useState, ReactNode } from 'react';
import { Agent, SimPost } from '@/data/mockData';
import { KnowledgeArtifact, ModelProviderId, PopulationArtifact } from '@/lib/console-api';

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
  guidingPrompts: string[];
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
  simPosts: SimPost[];
  chatHistory: Record<string, ChatHistoryEntry[]>;
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
  setGuidingPrompts: (prompts: string[]) => void;
  addGuidingPrompt: () => void;
  updateGuidingPrompt: (index: number, value: string) => void;
  removeGuidingPrompt: (index: number) => void;
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
  setSimPosts: (posts: SimPost[]) => void;
  addChatMessage: (threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>({
    currentStep: 1,
    completedSteps: [],
    sessionId: null,
    country: 'singapore',
    useCase: 'policy-review',
    modelProvider: 'ollama',
    modelName: 'qwen3:4b-instruct-2507-q4_K_M',
    embedModelName: 'nomic-embed-text',
    modelApiKey: '',
    modelBaseUrl: 'http://127.0.0.1:11434/v1/',
    uploadedFiles: [],
    guidingPrompts: [''],
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
    simPosts: [],
    chatHistory: {},
  });

  const setCurrentStep = useCallback((step: number) => setState(s => ({ ...s, currentStep: step })), []);
  const completeStep = useCallback((step: number) => setState(s => ({
    ...s,
    completedSteps: s.completedSteps.includes(step) ? s.completedSteps : [...s.completedSteps, step],
  })), []);
  const setSessionId = useCallback((sessionId: string | null) => setState(s => ({ ...s, sessionId })), []);
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
  const setGuidingPrompts = useCallback((prompts: string[]) => setState(s => ({ ...s, guidingPrompts: prompts })), []);
  const addGuidingPrompt = useCallback(() => setState(s => ({ ...s, guidingPrompts: [...s.guidingPrompts, ''] })), []);
  const updateGuidingPrompt = useCallback((index: number, value: string) => setState(s => ({
    ...s,
    guidingPrompts: s.guidingPrompts.map((p, i) => i === index ? value : p),
  })), []);
  const removeGuidingPrompt = useCallback((index: number) => setState(s => ({
    ...s,
    guidingPrompts: s.guidingPrompts.filter((_, i) => i !== index),
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
  const setSimPosts = useCallback((posts: SimPost[]) => setState(s => ({ ...s, simPosts: posts })), []);
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
    setGuidingPrompts,
    addGuidingPrompt,
    updateGuidingPrompt,
    removeGuidingPrompt,
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
    setSimPosts,
    addChatMessage,
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
    setGuidingPrompts,
    addGuidingPrompt,
    updateGuidingPrompt,
    removeGuidingPrompt,
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
    setSimPosts,
    addChatMessage,
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
