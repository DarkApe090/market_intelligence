import type { ReactNode } from 'react'
import { WorkspaceContext } from '../hooks/useWorkspaceContext'
import { useWorkspace } from '../hooks/useWorkspace'
import type { Session } from '../types'

export function WorkspaceProvider({
  session,
  onSessionChange,
  children,
}: {
  session: Session
  onSessionChange: () => Promise<void>
  children: ReactNode
}) {
  const workspace = useWorkspace(session, onSessionChange)
  return <WorkspaceContext.Provider value={workspace}>{children}</WorkspaceContext.Provider>
}
