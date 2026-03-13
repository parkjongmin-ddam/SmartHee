import { useState } from 'react'
import { createAgent } from '../api/client'
import type { Agent } from '../types'
import styles from './Panel.module.css'

interface Props {
  onAgentCreated: (agent: Agent) => void
}

const MODELS = [
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'anthropic/claude-3-5-sonnet-20241022',
  'anthropic/claude-3-haiku-20240307',
]

export default function BuilderPanel({ onAgentCreated }: Props) {
  const [request, setRequest] = useState('')
  const [model, setModel] = useState(MODELS[0])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Agent | null>(null)

  const handleCreate = async () => {
    if (!request.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await createAgent(request, model)
      setCreated(data)
      onAgentCreated(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '에이전트 생성 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.panel}>
      <p className={styles.desc}>
        자연어로 에이전트를 설명하면 AI가 자동으로 구성합니다.
      </p>

      <div className={styles.field}>
        <label className={styles.label}>모델</label>
        <select
          className={styles.select}
          value={model}
          onChange={e => setModel(e.target.value)}
          disabled={loading}
        >
          {MODELS.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.label}>에이전트 설명</label>
        <textarea
          className={styles.textarea}
          rows={5}
          placeholder="예: 웹 검색 후 요약하는 에이전트 만들어줘"
          value={request}
          onChange={e => setRequest(e.target.value)}
          disabled={loading}
        />
      </div>

      <button
        className={styles.btnPrimary}
        onClick={handleCreate}
        disabled={loading || !request.trim()}
      >
        {loading ? (
          <span className={styles.spinner}>생성 중...</span>
        ) : '에이전트 생성'}
      </button>

      {error && <div className={styles.error}>{error}</div>}

      {created && (
        <div className={styles.result}>
          <div className={styles.resultHeader}>
            <span className={styles.tag}>생성 완료</span>
            <span className={styles.agentName}>{created.config?.name}</span>
          </div>
          <div className={styles.kv}>
            <span className={styles.key}>model</span>
            <span className={styles.val}>{created.config?.model}</span>
          </div>
          <div className={styles.kv}>
            <span className={styles.key}>tools</span>
            <span className={styles.val}>
              {created.config?.tools?.length > 0
                ? created.config.tools.join(', ')
                : '없음'}
            </span>
          </div>
          <div className={styles.kv}>
            <span className={styles.key}>id</span>
            <span className={styles.val} style={{ fontSize: '10px', opacity: 0.6 }}>
              {created.agent_id}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
