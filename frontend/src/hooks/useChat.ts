import { useReducer, useCallback } from 'react';
import { consultAgent } from '../api/client';
import {
  extractContent,
  extractSpecialistFindings,
  extractDelegation,
  type Message,
  type QueryContext,
} from '../types';

type Action =
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'SET_PROCESSING'; processing: boolean }
  | { type: 'CLEAR' };

interface State { messages: Message[]; processing: boolean; }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'ADD_MESSAGE': return { ...state, messages: [...state.messages, action.message] };
    case 'SET_PROCESSING': return { ...state, processing: action.processing };
    case 'CLEAR': return { messages: [], processing: false };
    default: return state;
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(reducer, { messages: [], processing: false });

  const submit = useCallback(async (query: string, context: QueryContext) => {
    if (!query.trim() || state.processing) return;

    dispatch({ type: 'ADD_MESSAGE', message: { id: crypto.randomUUID(), role: 'user', content: query.trim() } });
    dispatch({ type: 'SET_PROCESSING', processing: true });

    try {
      const res = await consultAgent(query.trim(), context);
      const card = res.response_card;
      const content = extractContent(card);

      const msg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: content || (res.error ?? 'No response received'),
        sources: card?.documents,
        delegation: extractDelegation(card),
        specialistFindings: extractSpecialistFindings(card),
        reasoning: undefined,
        riskLevel: card?.payload?.risk_level as string | undefined,
        confidence: (card?.payload?.confidence_score as number | undefined) ?? card?.confidence,
        responseType: card?.response_type,
        processingTimeMs: res.processing_time_ms,
        isPartial: card?.response_type === 'PARTIAL',
        error: res.success === false ? (res.error ?? 'Unknown error') : undefined,
      };

      dispatch({ type: 'ADD_MESSAGE', message: msg });
    } finally {
      dispatch({ type: 'SET_PROCESSING', processing: false });
    }
  }, [state.processing]);

  const clear = useCallback(() => dispatch({ type: 'CLEAR' }), []);

  return { messages: state.messages, processing: state.processing, submit, clear };
}
