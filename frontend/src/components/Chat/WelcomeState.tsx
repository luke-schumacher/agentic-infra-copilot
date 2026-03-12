import styles from './WelcomeState.module.css';

const EXAMPLES = [
  {
    category: 'Symptom Diagnosis',
    prompts: [
      'MRI scanner shows intermittent RF pulse failures — possible cause?',
      'Gradient coil temperature spiking to 42°C during sequences',
    ],
  },
  {
    category: 'Hardware',
    prompts: [
      'What is the helium fill procedure for a 3T MAGNETOM Vida?',
      'Compatible gradient amplifiers for MAGNETOM Prisma?',
    ],
  },
  {
    category: 'Scheduling',
    prompts: [
      'Optimize scan slots for 2 MRI units and 18 patients',
      'Downtime impact analysis for a 72-hour magnet quench',
    ],
  },
];

export function WelcomeState({ onExampleClick }: { onExampleClick: (text: string) => void }) {
  return (
    <div className={styles.root}>
      <h1 className={styles.title}>What can I help with?</h1>
      <p className={styles.sub}>
        Ask about MRI scanner symptoms, hardware specifications, scheduling optimization, or operational analysis.
      </p>
      <div className={styles.grid}>
        {EXAMPLES.map((cat) => (
          <div key={cat.category} className={styles.category}>
            <span className={styles.catLabel}>{cat.category}</span>
            {cat.prompts.map((p) => (
              <button key={p} className={styles.prompt} onClick={() => onExampleClick(p)}>
                {p}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
