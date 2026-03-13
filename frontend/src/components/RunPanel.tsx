import { useState } from 'react'
import { runAgent } from '../api/client'
import type { Agent, RunResult } from '../types'
import styles from './Panel.module.css'

interface Props {
  agent: Agent | null
  onResult: (result: RunResult) => void
  onRunning: (v: boolean) => void
}

export default function RunPanel({ agent, onResult, onRunning }: Props) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    if (!agent || !input.trim()) return
    setLoading(true)
    setError(null)
    onRunning(true)
    try {
      const data = await runAgent(agent.agent_id, input)
      onResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '실행 실패')
    } finally {
      setLoading(false)
      onRunning(false)
    }
  }

  return (
    <div className={styles.panel}>
      {!agent ? (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>←</span>
          <p>먼저 에이전트를 생성하세요</p>
        </div>
      ) : (
        <>
          <div className={styles.agentBadge}>
            <span className={styles.dot} />
            <span className={styles.agentNameSm}>{agent.config?.name}</span>
            <span className={styles.agentModel}>{agent.config?.model}</span>
          </div>

          <p className={styles.desc}>
            에이전트에게 실행할 태스크를 입력하세요.
          </p>

          <div className={styles.field}>
            <label className={styles.label}>태스크 입력</label>
            <textarea
              className={styles.textarea}
              rows={6}
              placeholder="예: ADFS에 대해 설명해줘"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={loading}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRun()
              }}
            />
            <span className={styles.hint}>⌘ + Enter 로 실행</span>
          </div>

          <button
            className={styles.btnPrimary}
            onClick={handleRun}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <span className={styles.spinner}>실행 중...</span>
            ) : '▶ 실행'}
          </button>

          {error && <div className={styles.error}>{error}</div>}
        </>
      )}
    </div>
  )
}
