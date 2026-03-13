import type { RunResult } from '../types'
import styles from './Panel.module.css'

interface Props {
  result: RunResult | null
  isRunning: boolean
}

export default function ResultPanel({ result, isRunning }: Props) {
  if (isRunning) {
    return (
      <div className={styles.panel}>
        <div className={styles.running}>
          <div className={styles.runningDots}>
            <span /><span /><span />
          </div>
          <p className={styles.runningText}>에이전트 실행 중...</p>
          <p className={styles.runningSubtext}>LLM이 응답을 생성하고 있습니다</p>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className={styles.panel}>
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>◎</span>
          <p>실행 결과가 여기 표시됩니다</p>
        </div>
      </div>
    )
  }

  const isSuccess = result.status === 'success'

  return (
    <div className={styles.panel}>
      <div className={styles.resultMeta}>
        <span className={isSuccess ? styles.tagSuccess : styles.tagError}>
          {isSuccess ? '✓ SUCCESS' : '✗ FAILED'}
        </span>
        <span className={styles.runId}>
          {result.run_id?.slice(0, 8)}...
        </span>
      </div>

      <div className={styles.outputBox}>
        <div className={styles.outputLabel}>OUTPUT</div>
        <div className={styles.outputText}>
          {result.output}
        </div>
      </div>

      <button
        className={styles.btnSecondary}
        onClick={() => navigator.clipboard.writeText(result.output)}
      >
        복사
      </button>
    </div>
  )
}
