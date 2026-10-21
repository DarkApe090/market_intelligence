import { createContext, useContext } from 'react'
import type { Workspace } from './useWorkspace'

export const WorkspaceContext = createContext<Workspace | null>(null)

export function useWorkspaceContext() {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('WorkspaceProvider em falta')
  return value
}
