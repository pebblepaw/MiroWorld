import { ChatPane } from '../../components/chat/ChatPane';
import { Panel } from '../../components/layout/Panel';
import type { InteractionHub } from '../../types/console';

type Props = {
  hub: InteractionHub | null;
  selectedAgentId: string | null;
  reportPrompt: string;
  agentPrompt: string;
  isHubBusy: boolean;
  isReportBusy: boolean;
  isAgentBusy: boolean;
  onReportPromptChange: (value: string) => void;
  onReportSubmit: () => void;
  onAgentPromptChange: (value: string) => void;
  onAgentSubmit: () => void;
  onSelectAgent: (agentId: string) => void;
  onReloadHub: () => void;
};

export function Stage5HubScreen(props: Props) {
  const selectedAgent = props.hub?.selected_agent ?? null;
  const selectedAgentId = props.selectedAgentId ?? props.hub?.selected_agent_id ?? selectedAgent?.agent_id ?? null;
  const selectedAgentMatches = selectedAgentId && selectedAgent ? String(selectedAgent.agent_id) === String(selectedAgentId) : false;
  const reportTranscript = props.hub?.report_agent?.transcript ?? [];
  const agentTranscript = selectedAgentMatches ? selectedAgent?.transcript ?? [] : [];

  return (
    <div className="mk-screen-grid mk-screen-grid--hub">
      <Panel eyebrow="Stage 5" title="Unified Interaction Hub">
        <div className="mk-panel__toolbar">
          <button className="mk-button" type="button" onClick={props.onReloadHub} disabled={props.isHubBusy}>
            {props.isHubBusy ? 'Reloading…' : 'Reload Hub State'}
          </button>
          <div className="mk-status">{selectedAgentId ? `Selected agent ${selectedAgentId}` : 'No agent selected'}</div>
        </div>
        <div className="mk-list">
          {(props.hub?.influential_agents ?? []).slice(0, 6).map((agent) => {
            const isActive = String(agent.agent_id) === selectedAgentId;
            return (
              <button
                key={String(agent.agent_id)}
                type="button"
                className={isActive ? 'mk-list-card mk-list-card--selectable mk-list-card--active' : 'mk-list-card mk-list-card--selectable'}
                onClick={() => props.onSelectAgent(String(agent.agent_id))}
              >
                <div className="mk-list-card__title-row">
                  <div className="mk-list-card__title">{String(agent.agent_id ?? 'agent')}</div>
                  {isActive ? <span className="mk-chip">Active</span> : null}
                </div>
                <div className="mk-list-card__meta">{String(agent.planning_area ?? 'Unknown')}</div>
                <p>{String(agent.latest_argument ?? 'No recent argument captured.')}</p>
              </button>
            );
          })}
        </div>
      </Panel>

      <ChatPane
        title="Report Agent"
        promptLabel="Ask the report agent"
        value={props.reportPrompt}
        transcript={reportTranscript}
        context={String(props.hub?.report_agent?.starter_prompt ?? 'Ask about dissent clusters, mitigation options, or demographic shifts.')}
        sendLabel="Ask Report Agent"
        isBusy={props.isReportBusy}
        onChange={props.onReportPromptChange}
        onSubmit={props.onReportSubmit}
      />

      <ChatPane
        title="Selected Agent"
        promptLabel="Ask the selected persona"
        value={props.agentPrompt}
        transcript={agentTranscript}
        context={
          selectedAgentMatches && selectedAgent
            ? `Influential agent ${String(selectedAgent.agent_id)} · ${String(selectedAgent.planning_area ?? 'Unknown')} · ${String(
                selectedAgent.latest_argument ?? 'No recent argument captured.',
              )}`
            : selectedAgentId
              ? 'Reloading the selected agent hub state...'
              : 'Select an influential agent to load its hub state and transcript.'
        }
        sendLabel="Ask Selected Agent"
        isBusy={props.isAgentBusy}
        onChange={props.onAgentPromptChange}
        onSubmit={props.onAgentSubmit}
      />
    </div>
  );
}
