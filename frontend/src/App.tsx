import { useState, useCallback } from 'react';
import { Header } from './components/Header/Header';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatArea } from './components/Chat/ChatArea';
import { ContextRow } from './components/InputBar/ContextRow';
import { InputBar } from './components/InputBar/InputBar';
import { EvaluationPanel } from './components/Evaluation/EvaluationPanel';
import { useChat } from './hooks/useChat';
import { useAgentHealth } from './hooks/useAgentHealth';
import type { QueryContext } from './types';
import './styles/globals.css';

const DEFAULT_CTX: QueryContext = {
  customer_id: '',
  scanner_model: '',
  institution_type: '',
  location: '',
  query_type: 'general',
};

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [evalPanelOpen, setEvalPanelOpen] = useState(false);
  const [context, setContext] = useState<QueryContext>(DEFAULT_CTX);
  const [inputValue, setInputValue] = useState('');

  const { messages, processing, submit } = useChat();
  const { agents, loading: agentsLoading, refresh } = useAgentHealth();

  const handleSubmit = useCallback(() => {
    if (!inputValue.trim() || processing) return;
    submit(inputValue, context);
    setInputValue('');
  }, [inputValue, context, processing, submit]);

  const handleExample = useCallback((text: string) => {
    submit(text, context);
  }, [context, submit]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Header onMenuClick={() => setSidebarOpen(true)} agents={agents} onEvalClick={() => setEvalPanelOpen(true)} />
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        agents={agents}
        onRefresh={refresh}
        refreshing={agentsLoading}
      />
      <main style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', marginTop: 52 }}>
        <ChatArea messages={messages} onExampleClick={handleExample} />
        <ContextRow context={context} onChange={setContext} />
        <InputBar value={inputValue} onChange={setInputValue} onSubmit={handleSubmit} processing={processing} />
      </main>
      <EvaluationPanel open={evalPanelOpen} onClose={() => setEvalPanelOpen(false)} />
    </div>
  );
}
