import { useState, createContext, useContext, useEffect } from 'react'
import type { Theme } from './types'
import Dashboard from './pages/Dashboard'

/* ── Theme Context ── */
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void }>({
  theme: 'dark',
  toggle: () => {},
})
export const useTheme = () => useContext(ThemeCtx)

export default function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem('af-theme') as Theme) || 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('af-theme', theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))

  return (
    <ThemeCtx.Provider value={{ theme, toggle }}>
      <Dashboard />
    </ThemeCtx.Provider>
  )
}
