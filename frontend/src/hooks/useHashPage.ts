import { useEffect, useState } from 'react'
import { pageFromHash } from '../lib/format'

export function useHashPage() {
  const [page, setPage] = useState(pageFromHash)

  useEffect(() => {
    const sync = () => setPage(pageFromHash())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  return page
}
