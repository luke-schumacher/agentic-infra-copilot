import { useEffect, useRef } from 'react';
import styles from './ChatArea.module.css';
import { WelcomeState } from './WelcomeState';
import { UserBubble } from './UserBubble';
import { AssistantBubble } from './AssistantBubble';
import type { Message } from '../../types';

interface Props {
  messages: Message[];
  onExampleClick: (text: string) => void;
}

export function ChatArea({ messages, onExampleClick }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className={styles.area}>
      {messages.length === 0 ? (
        <WelcomeState onExampleClick={onExampleClick} />
      ) : (
        <div className={styles.messages}>
          {messages.map((m) =>
            m.role === 'user'
              ? <UserBubble key={m.id} content={m.content} />
              : <AssistantBubble key={m.id} message={m} />
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
