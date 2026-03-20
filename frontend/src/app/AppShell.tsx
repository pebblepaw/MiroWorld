import { useEffect, useMemo, useState } from 'react';
import * as echarts from 'echarts';
import { getDefaultScreen, getScreenFromLocation, pushScreen } from './screen-state';
import {
  createSession,
  getInteractionHub,
  getPlanningAreaGeoJson,
  getReportFrictionMap,
  getReportFull,
  getReportOpinions,
  getSimulationState,
  loadDemoBundle,
  previewPopulation,
  processKnowledge,
  postAgentChat,
  postReportChat,
  startSimulation,
  uploadKnowledge,
  subscribeSimulationStream,
} from '../api/console';
import type {
  ConsoleMode,
  GraphView,
  InteractionHub,
  KnowledgeArtifact,
  PopulationArtifact,
  ReportFrictionMap,
  ReportFull,
  ReportOpinions,
  ScreenKey,
  SimulationEvent,
  SimulationState,
} from '../types/console';
import { StageNav } from '../components/layout/StageNav';
import { TopBar } from '../components/layout/TopBar';
import { Stage1Screen } from '../screens/stage1/Stage1Screen';
import { Stage2Screen } from '../screens/stage2/Stage2Screen';
import { Stage3Screen } from '../screens/stage3/Stage3Screen';
import { Stage4ReportScreen } from '../screens/stage4/Stage4ReportScreen';
import { Stage4OpinionsScreen } from '../screens/stage4/Stage4OpinionsScreen';
import { Stage4FrictionScreen } from '../screens/stage4/Stage4FrictionScreen';
import { Stage5HubScreen } from '../screens/stage5/Stage5HubScreen';

const defaultSessionId = 'mckainsey-console';
const configuredMode = String(import.meta.env.VITE_BOOT_MODE ?? 'demo').toLowerCase() === 'live' ? 'live' : 'demo';

export default function AppShell() {
  const [screen, setScreen] = useState<ScreenKey>(getScreenFromLocation());
  const [mode, setMode] = useState<ConsoleMode>(configuredMode);
  const [graphView, setGraphView] = useState<GraphView>('knowledge');
  const [sessionId, setSessionId] = useState(defaultSessionId);
  const [knowledge, setKnowledge] = useState<KnowledgeArtifact | null>(null);
  const [population, setPopulation] = useState<PopulationArtifact | null>(null);
  const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [reportFull, setReportFull] = useState<ReportFull | null>(null);
  const [reportOpinions, setReportOpinions] = useState<ReportOpinions | null>(null);
  const [reportFriction, setReportFriction] = useState<ReportFrictionMap | null>(null);
  const [hub, setHub] = useState<InteractionHub | null>(null);
  const [documentText, setDocumentText] = useState('');
  const [demographicFocus, setDemographicFocus] = useState('seniors in Woodlands affected by transport affordability changes');
  const [planningAreas, setPlanningAreas] = useState('Woodlands,Yishun');
  const [policySummary, setPolicySummary] = useState('Singapore FY2026 budget support focused on transport affordability, retirement resilience, and household cost pressure.');
  const [agentCount, setAgentCount] = useState(50);
  const [rounds, setRounds] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('booting');
  const [reportPrompt, setReportPrompt] = useState('What is the highest-friction planning area and why?');
  const [agentPrompt, setAgentPrompt] = useState('What changed your position during deliberation?');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [hubBusy, setHubBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [agentBusy, setAgentBusy] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const onHashChange = () => setScreen(getScreenFromLocation());
    window.addEventListener('hashchange', onHashChange);
    if (!window.location.hash) {
      pushScreen(getDefaultScreen());
    }
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const geoJson = await getPlanningAreaGeoJson();
        echarts.registerMap('sg-planning-areas', geoJson as never);
        if (!cancelled) {
          setMapReady(true);
        }
      } catch {
        if (!cancelled) {
          setMapReady(false);
        }
      }

      try {
        if (mode === 'demo') {
          const demo = await loadDemoBundle();
          if (cancelled) return;
          setSessionId(demo.session.session_id);
          setKnowledge(demo.knowledge);
          setPopulation(demo.population);
          setSimulationState(demo.simulationState);
          setEvents(demo.simulationState?.recent_events ?? []);
          setReportFull(demo.reportFull);
          setReportOpinions(demo.reportOpinions);
          setReportFriction(demo.reportFriction);
          setHub(demo.interactionHub);
          setSelectedAgentId(demo.interactionHub?.selected_agent_id ?? demo.interactionHub?.selected_agent?.agent_id ?? null);
          setStatus('demo-ready');
          return;
        }

        const session = await createSession(defaultSessionId, 'live');
        if (cancelled) return;
        setSessionId(session.session_id);
        setStatus('live-session-ready');
      } catch (err) {
        if (!cancelled) {
          setError(String((err as Error).message ?? err));
          setStatus('bootstrap-failed');
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  useEffect(() => {
    if (mode !== 'live' || !sessionId || simulationState?.status !== 'running') {
      return;
    }
    const unsubscribe = subscribeSimulationStream(
      sessionId,
      (event) => {
        setEvents((current) => [...current, event]);
        if (event.metrics) {
          setSimulationState((current) =>
            current
              ? {
                  ...current,
                  event_count: current.event_count + 1,
                  last_round: Math.max(current.last_round, event.round_no ?? 0),
                  latest_metrics: event.metrics ?? current.latest_metrics,
                  recent_events: [...current.recent_events, event].slice(-10),
                }
              : current,
          );
        }
      },
      () => setStatus('stream-open'),
      () => setStatus('stream-error'),
    );
    return unsubscribe;
  }, [mode, sessionId, simulationState?.status]);

  async function handleUseDemoDocument() {
    setUploadedFile(null);
    setDocumentText('Singapore FY2026 budget support targeted at transport affordability, retirement resilience, and household cost pressure in northern planning areas.');
  }

  async function handleProcessKnowledge() {
    setBusy(true);
    setError('');
    try {
      const liveSession = mode === 'live' ? await createSession(sessionId, 'live') : null;
      const activeSessionId = liveSession?.session_id ?? sessionId;
      if (liveSession) setSessionId(activeSessionId);

      const artifact = uploadedFile
        ? await uploadKnowledge(activeSessionId, {
            file: uploadedFile,
            demographicFocus,
          })
        : await processKnowledge(activeSessionId, {
            documentText: documentText || undefined,
            demographicFocus,
            useDefaultDemoDocument: !documentText,
          });
      setKnowledge(artifact);
      setStatus('knowledge-ready');
      pushScreen('stage-2');
      setScreen('stage-2');
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSamplePopulation() {
    setBusy(true);
    setError('');
    try {
      const artifact = await previewPopulation(sessionId, {
        agentCount,
        planningAreas: planningAreas.split(',').map((item) => item.trim()).filter(Boolean),
      });
      setPopulation(artifact);
      setStatus('population-ready');
      pushScreen('stage-3');
      setScreen('stage-3');
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setBusy(false);
    }
  }

  async function loadReports(targetSessionId: string, targetAgentId?: string | null) {
    const [full, opinions, friction, interaction] = await Promise.all([
      getReportFull(targetSessionId),
      getReportOpinions(targetSessionId),
      getReportFrictionMap(targetSessionId),
      getInteractionHub(targetSessionId, targetAgentId ?? undefined),
    ]);
    setReportFull(full);
    setReportOpinions(opinions);
    setReportFriction(friction);
    setHub(interaction);
    setSelectedAgentId(interaction.selected_agent_id ?? interaction.selected_agent?.agent_id ?? targetAgentId ?? null);
  }

  async function refreshHubState(targetAgentId = selectedAgentId) {
    setHubBusy(true);
    setError('');
    try {
      const interaction = await getInteractionHub(sessionId, targetAgentId ?? undefined);
      setHub(interaction);
      setSelectedAgentId(interaction.selected_agent_id ?? interaction.selected_agent?.agent_id ?? targetAgentId ?? null);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setHubBusy(false);
    }
  }

  async function handleStartSimulation() {
    setBusy(true);
    setError('');
    try {
      const state = await startSimulation(sessionId, { policySummary, rounds, mode });
      setSimulationState(state);
      setEvents(state.recent_events ?? []);
      setStatus(state.status);
      if (mode === 'demo') {
        const latestState = await getSimulationState(sessionId);
        setSimulationState(latestState);
      }
      window.setTimeout(() => {
        void loadReports(sessionId, selectedAgentId);
      }, 1000);
      pushScreen('stage-4-report');
      setScreen('stage-4-report');
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setBusy(false);
    }
  }

  async function handleReportSubmit() {
    if (reportBusy || !reportPrompt.trim()) {
      return;
    }
    setReportBusy(true);
    setError('');
    try {
      await postReportChat(sessionId, reportPrompt.trim());
      setReportPrompt('');
      await refreshHubState(selectedAgentId);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setReportBusy(false);
    }
  }

  async function handleAgentSubmit() {
    const effectiveAgentId = selectedAgentId ?? hub?.selected_agent_id ?? hub?.influential_agents[0]?.agent_id ?? null;
    if (agentBusy || !effectiveAgentId || !agentPrompt.trim()) {
      return;
    }
    setAgentBusy(true);
    setError('');
    try {
      await postAgentChat(sessionId, effectiveAgentId, agentPrompt.trim());
      setAgentPrompt('');
      await refreshHubState(effectiveAgentId);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleSelectAgent(agentId: string) {
    setSelectedAgentId(agentId);
    await refreshHubState(agentId);
  }

  const activeScreen = useMemo(() => {
    switch (screen) {
      case 'stage-1':
        return (
          <Stage1Screen
            knowledge={knowledge}
            documentText={documentText}
            demographicFocus={demographicFocus}
            uploadedFile={uploadedFile}
            isBusy={busy}
            onDocumentTextChange={setDocumentText}
            onDemographicFocusChange={setDemographicFocus}
            onUploadedFileChange={setUploadedFile}
            onUseDemoDocument={handleUseDemoDocument}
            onProcess={handleProcessKnowledge}
          />
        );
      case 'stage-2':
        return (
          <Stage2Screen
            population={population}
            agentCount={agentCount}
            planningAreas={planningAreas}
            onAgentCountChange={setAgentCount}
            onPlanningAreasChange={setPlanningAreas}
            onSample={handleSamplePopulation}
            isBusy={busy}
          />
        );
      case 'stage-3':
        return (
          <Stage3Screen
            mode={mode}
            state={simulationState}
            events={events}
            policySummary={policySummary}
            rounds={rounds}
            onPolicySummaryChange={setPolicySummary}
            onRoundsChange={setRounds}
            onStart={handleStartSimulation}
            isBusy={busy}
          />
        );
      case 'stage-4-report':
        return <Stage4ReportScreen report={reportFull} />;
      case 'stage-4-opinions':
        return <Stage4OpinionsScreen opinions={reportOpinions} />;
      case 'stage-4-friction':
        return <Stage4FrictionScreen friction={reportFriction} mapReady={mapReady} />;
      case 'stage-5-hub':
        return (
          <Stage5HubScreen
            hub={hub}
            selectedAgentId={selectedAgentId}
            reportPrompt={reportPrompt}
            agentPrompt={agentPrompt}
            isHubBusy={hubBusy}
            isReportBusy={reportBusy}
            isAgentBusy={agentBusy}
            onReportPromptChange={setReportPrompt}
            onReportSubmit={handleReportSubmit}
            onAgentPromptChange={setAgentPrompt}
            onAgentSubmit={handleAgentSubmit}
            onSelectAgent={handleSelectAgent}
            onReloadHub={() => {
              void refreshHubState(selectedAgentId);
            }}
          />
        );
      default:
        return null;
    }
  }, [
    agentCount,
    agentPrompt,
    busy,
    demographicFocus,
    documentText,
    events,
    hubBusy,
    hub,
    knowledge,
    mapReady,
    mode,
    planningAreas,
    policySummary,
    population,
    reportBusy,
    reportFriction,
    reportFull,
    reportOpinions,
    reportPrompt,
    rounds,
    selectedAgentId,
    screen,
    simulationState,
    uploadedFile,
    agentBusy,
  ]);

  return (
    <div className="mk-app">
      <StageNav
        active={screen}
        onSelect={(nextScreen) => {
          setScreen(nextScreen);
          pushScreen(nextScreen);
        }}
      />
      <main className="mk-main">
        <TopBar
          screen={screen}
          mode={mode}
          graphView={graphView}
          sessionId={sessionId}
          status={status}
          onGraphViewChange={setGraphView}
          onModeChange={setMode}
        />
        {error ? <div className="mk-error">{error}</div> : null}
        <div className="mk-status">Graph View: {graphView}</div>
        {activeScreen}
      </main>
    </div>
  );
}
