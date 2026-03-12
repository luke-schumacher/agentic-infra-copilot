import { useState, useEffect, useCallback } from 'react';
import { checkHealth } from '../api/client';
import { AGENTS, type AgentHealthStatus } from '../types';

export type AgentHealthMap = Record<string, AgentHealthStatus>;

export function useAgentHealth() {
  const [agents, setAgents] = useState<AgentHealthMap>({});
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const results = await Promise.all(
      AGENTS.map(async (a) => [a.id, await checkHealth(a.url)] as const)
    );
    setAgents(Object.fromEntries(results));
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { agents, loading, refresh };
}
