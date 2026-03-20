import { useState, useRef, useEffect } from 'react';
import { Search, Send } from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { agentResponses, Agent } from '@/data/mockData';

export default function AgentChat() {
  const { agents, chatHistory, addChatMessage } = useApp();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const [filterSentiment, setFilterSentiment] = useState<string>('all');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const filteredAgents = agents.filter(a => {
    const matchSearch = a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.occupation.toLowerCase().includes(search.toLowerCase()) ||
      a.planningArea.toLowerCase().includes(search.toLowerCase());
    const matchSentiment = filterSentiment === 'all' || a.sentiment === filterSentiment;
    return matchSearch && matchSentiment;
  }).slice(0, 50);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, selectedAgent]);

  const sendMessage = () => {
    if (!message.trim() || !selectedAgent) return;
    addChatMessage(selectedAgent.id, 'user', message);
    setMessage('');
    setTimeout(() => {
      const responses = agentResponses[selectedAgent.sentiment];
      const reply = responses[Math.floor(Math.random() * responses.length)];
      addChatMessage(selectedAgent.id, 'agent', reply);
    }, 800 + Math.random() * 1000);
  };

  const sentimentColor = (s: string) => {
    if (s === 'positive') return 'bg-success';
    if (s === 'negative') return 'bg-destructive';
    return 'bg-secondary';
  };

  const history = selectedAgent ? (chatHistory[selectedAgent.id] || []) : [];

  return (
    <div className="flex h-full p-6 gap-6 overflow-hidden">
      {/* Agent List */}
      <GlassCard className="w-72 flex-shrink-0 flex flex-col gap-3 p-4 h-full border-white/5 bg-black/20">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search agents..."
            className="pl-9 bg-black/40 border-white/10 focus-visible:ring-primary/50"
          />
        </div>
        <div className="flex gap-1.5">
          {['all', 'positive', 'neutral', 'negative'].map(s => (
            <button
              key={s}
              onClick={() => setFilterSentiment(s)}
              className={`text-[10px] px-2 py-1 rounded-full border transition-all capitalize ${
                filterSentiment === s ? 'bg-primary/20 border-primary/50 text-primary shadow-[0_0_10px_rgba(255,100,0,0.2)]' : 'border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto space-y-1.5 scrollbar-thin pr-1">
          {filteredAgents.map(agent => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent)}
              className={`w-full text-left p-3 rounded-xl transition-all duration-300 group ${
                selectedAgent?.id === agent.id ? 'bg-gradient-to-r from-primary/20 to-transparent border border-primary/30 shadow-[0_0_15px_rgba(255,100,0,0.1)]' : 'hover:bg-white/5 border border-transparent hover:border-white/10'
              }`}
            >
              <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${selectedAgent?.id === agent.id ? 'bg-primary/20 text-primary' : 'bg-black/40 text-muted-foreground group-hover:text-foreground'}`}>
                  <span className="text-xs font-bold">{agent.name.split(' ').map(n => n[0]).join('').slice(0, 2)}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs font-medium truncate transition-colors ${selectedAgent?.id === agent.id ? 'text-primary' : 'text-foreground'}`}>{agent.name}</span>
                    <span className={`w-2 h-2 rounded-full ${sentimentColor(agent.sentiment)} flex-shrink-0 shadow-[0_0_5px_currentColor] opacity-80`} />
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate">{agent.occupation} · {agent.planningArea}</div>
                </div>
              </div>
            </button>
          ))}
          {agents.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">Generate agents first (Step 2)</p>
          )}
        </div>
      </GlassCard>

      {/* Chat Panel */}
      <GlassCard className="flex-1 flex flex-col min-w-0 h-full p-4 border-white/5 bg-black/20">
        {selectedAgent ? (
          <>
            {/* Agent Header */}
            <div className="p-4 mb-4 rounded-xl bg-gradient-to-r from-primary/10 to-transparent border border-primary/20 shadow-[0_0_20px_rgba(255,100,0,0.05)] flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center shadow-[0_0_15px_rgba(255,100,0,0.2)]">
                  <span className="text-primary font-bold">{selectedAgent.name.split(' ').map(n => n[0]).join('').slice(0, 2)}</span>
                </div>
                <div>
                  <div className="text-sm font-semibold text-foreground">{selectedAgent.name}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {selectedAgent.age}y · {selectedAgent.gender} · {selectedAgent.ethnicity} · {selectedAgent.occupation} · {selectedAgent.planningArea}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-1.5 bg-black/40 px-3 py-1.5 rounded-full border border-white/5">
                  <span className={`w-2 h-2 rounded-full ${sentimentColor(selectedAgent.sentiment)} shadow-[0_0_5px_currentColor]`} />
                  <span className="text-xs text-muted-foreground capitalize">{selectedAgent.sentiment}</span>
                  <div className="w-px h-3 bg-white/10 mx-1" />
                  <span className="text-xs font-mono text-primary">{selectedAgent.approvalScore}% approval</span>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 scrollbar-thin pr-2 mb-4">
              {history.length === 0 && (
                <div className="text-center text-muted-foreground text-sm py-12">
                  Start a conversation with {selectedAgent.name.split(' ')[0]}
                </div>
              )}
              {history.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[70%] rounded-2xl px-4 py-2.5 text-sm shadow-lg ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-primary to-orange-600 text-white rounded-tr-sm'
                      : 'bg-black/40 border border-white/10 text-foreground rounded-tl-sm backdrop-blur-md'
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="flex gap-2 flex-shrink-0 pt-2">
              <Input
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder={`Ask ${selectedAgent.name.split(' ')[0]} about the policy...`}
                className="bg-black/40 border-white/10 focus-visible:ring-primary/50 h-12 rounded-xl"
              />
              <Button onClick={sendMessage} size="icon" className="h-12 w-12 rounded-xl bg-gradient-to-br from-primary to-orange-600 text-white shadow-[0_0_15px_rgba(255,100,0,0.3)] hover:shadow-[0_0_25px_rgba(255,100,0,0.5)] transition-all flex-shrink-0 border-none">
                <Send className="w-5 h-5" />
              </Button>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <div className="flex flex-col items-center gap-4 opacity-50">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                <Search className="w-8 h-8" />
              </div>
              <p>Select an agent from the list to start chatting</p>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
