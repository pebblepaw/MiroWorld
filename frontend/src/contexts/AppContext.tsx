import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Agent, SimPost } from '@/data/mockData';
import { KnowledgeArtifact } from '@/lib/console-api';

interface AppState {
  currentStep: number;
  completedSteps: number[];
  sessionId: string | null;
  uploadedFile: File | null;
  guidingPrompt: string;
  knowledgeGraphReady: boolean;
  knowledgeArtifact: KnowledgeArtifact | null;
  knowledgeLoading: boolean;
  knowledgeError: string | null;
  agentCount: number;
  agents: Agent[];
  agentsGenerated: boolean;
  simulationRounds: number;
  simulationComplete: boolean;
  simPosts: SimPost[];
  chatHistory: Record<string, { role: 'user' | 'agent'; content: string }[]>;
}

interface AppContextType extends AppState {
  setCurrentStep: (step: number) => void;
  completeStep: (step: number) => void;
  setSessionId: (sessionId: string | null) => void;
  setUploadedFile: (file: File | null) => void;
  setGuidingPrompt: (prompt: string) => void;
  setKnowledgeGraphReady: (ready: boolean) => void;
  setKnowledgeArtifact: (artifact: KnowledgeArtifact | null) => void;
  setKnowledgeLoading: (loading: boolean) => void;
  setKnowledgeError: (error: string | null) => void;
  setAgentCount: (count: number) => void;
  setAgents: (agents: Agent[]) => void;
  setAgentsGenerated: (gen: boolean) => void;
  setSimulationRounds: (rounds: number) => void;
  setSimulationComplete: (complete: boolean) => void;
  setSimPosts: (posts: SimPost[]) => void;
  addChatMessage: (agentId: string, role: 'user' | 'agent', content: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>({
    currentStep: 1,
    completedSteps: [],
    sessionId: null,
    uploadedFile: null,
    guidingPrompt: '',
    knowledgeGraphReady: false,
    knowledgeArtifact: null,
    knowledgeLoading: false,
    knowledgeError: null,
    agentCount: 500,
    agents: [],
    agentsGenerated: false,
    simulationRounds: 3,
    simulationComplete: false,
    simPosts: [],
    chatHistory: {},
  });

  const setCurrentStep = (step: number) => setState(s => ({ ...s, currentStep: step }));
  const completeStep = (step: number) => setState(s => ({
    ...s,
    completedSteps: s.completedSteps.includes(step) ? s.completedSteps : [...s.completedSteps, step],
  }));
  const setSessionId = (sessionId: string | null) => setState(s => ({ ...s, sessionId }));
  const setUploadedFile = (file: File | null) => setState(s => ({ ...s, uploadedFile: file }));
  const setGuidingPrompt = (prompt: string) => setState(s => ({ ...s, guidingPrompt: prompt }));
  const setKnowledgeGraphReady = (ready: boolean) => setState(s => ({ ...s, knowledgeGraphReady: ready }));
  const setKnowledgeArtifact = (knowledgeArtifact: KnowledgeArtifact | null) => setState(s => ({ ...s, knowledgeArtifact }));
  const setKnowledgeLoading = (knowledgeLoading: boolean) => setState(s => ({ ...s, knowledgeLoading }));
  const setKnowledgeError = (knowledgeError: string | null) => setState(s => ({ ...s, knowledgeError }));
  const setAgentCount = (count: number) => setState(s => ({ ...s, agentCount: count }));
  const setAgents = (agents: Agent[]) => setState(s => ({ ...s, agents }));
  const setAgentsGenerated = (gen: boolean) => setState(s => ({ ...s, agentsGenerated: gen }));
  const setSimulationRounds = (rounds: number) => setState(s => ({ ...s, simulationRounds: rounds }));
  const setSimulationComplete = (complete: boolean) => setState(s => ({ ...s, simulationComplete: complete }));
  const setSimPosts = (posts: SimPost[]) => setState(s => ({ ...s, simPosts: posts }));
  const addChatMessage = (agentId: string, role: 'user' | 'agent', content: string) => {
    setState(s => ({
      ...s,
      chatHistory: {
        ...s.chatHistory,
        [agentId]: [...(s.chatHistory[agentId] || []), { role, content }],
      },
    }));
  };

  return (
    <AppContext.Provider value={{
      ...state, setCurrentStep, completeStep, setSessionId, setUploadedFile, setGuidingPrompt,
      setKnowledgeGraphReady, setKnowledgeArtifact, setKnowledgeLoading, setKnowledgeError,
      setAgentCount, setAgents, setAgentsGenerated,
      setSimulationRounds, setSimulationComplete, setSimPosts, addChatMessage,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
