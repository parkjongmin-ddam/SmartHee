import { useState } from 'react'
import Header from '../components/Header'
import BuilderPanel from '../components/BuilderPanel'
import RunPanel from '../components/RunPanel'
import ResultPanel from '../components/ResultPanel'
import type { Agent, RunResult } from '../types'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  return (
    <div className={styles.layout}>
      <Header />
      <main className={styles.main}>

        {/* 왼쪽 — 에이전트 생성 */}
        <section className={styles.col}>
          <SectionLabel index="01" label="AGENT BUILDER" />
          <BuilderPanel onAgentCreated={setAgent} />
        </section>

        {/* 가운데 — 실행 */}
        <section className={styles.col}>
          <SectionLabel index="02" label="EXECUTE" />
          <RunPanel
            agent={agent}
            onResult={setResult}
            onRunning={setIsRunning}
          />
        </section>

        {/* 오른쪽 — 결과 */}
        <section className={styles.col}>
          <SectionLabel index="03" label="RESULT" />
          <ResultPanel result={result} isRunning={isRunning} />
        </section>

      </main>
    </div>
  )
}

function SectionLabel({ index, label }: { index: string; label: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      marginBottom: '16px',
    }}>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '10px',
        color: 'var(--text-accent)',
        letterSpacing: '0.1em',
      }}>{index}</span>
      <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '10px',
        color: 'var(--text-muted)',
        letterSpacing: '0.15em',
      }}>{label}</span>
    </div>
  )
}
