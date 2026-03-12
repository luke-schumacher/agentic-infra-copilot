import { useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import styles from './InputBar.module.css';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  processing: boolean;
}

export function InputBar({ value, onChange, onSubmit, processing }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto';
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 140)}px`;
    }
  }, [value]);

  return (
    <div className={styles.bar}>
      <textarea
        ref={ref}
        className={styles.textarea}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!processing && value.trim()) onSubmit();
          }
        }}
        placeholder="Ask about scanner symptoms, hardware specs, or scheduling…"
        disabled={processing}
        rows={1}
      />
      <button
        className={styles.sendBtn}
        onClick={onSubmit}
        disabled={processing || !value.trim()}
        aria-label="Send"
      >
        {processing
          ? <Loader2 size={16} className={styles.spinning} />
          : <Send size={16} />}
      </button>
    </div>
  );
}
