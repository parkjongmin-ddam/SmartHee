export interface Agent {
  agent_id: string
  config: {
    name: string
    description: string
    model: string
    tools: string[]
    system_prompt: string
  }
}

export interface RunResult {
  run_id: string
  output: string
  status: 'success' | 'failed'
}

export interface TaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE'
  result: RunResult | null
}

export type Theme = 'dark' | 'light'
