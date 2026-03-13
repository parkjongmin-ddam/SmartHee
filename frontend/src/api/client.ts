const BASE = '/api/v1'

export async function createAgent(request: string, model = 'openai/gpt-4o') {
  const res = await fetch(`${BASE}/builder/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request, model }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function runAgent(agentId: string, input: string) {
  const res = await fetch(`${BASE}/agents/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, input }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function runAgentAsync(agentId: string, inputText: string, callbackUrl: string) {
  const res = await fetch(`${BASE}/webhook/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, input_text: inputText, callback_url: callbackUrl }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getTaskStatus(taskId: string) {
  const res = await fetch(`${BASE}/webhook/status/${taskId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getModels() {
  const res = await fetch(`${BASE}/models`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
