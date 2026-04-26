import { useQuery } from '@tanstack/react-query'
import { client } from '../api/client'

export function useHealth() {
  const q = useQuery({
    queryKey: ['health'],
    queryFn: () => client.get('/health').then((r) => r.data as { status: string }),
    refetchInterval: 10_000,
    retry: 1,
  })
  return {
    online: q.data?.status === 'ok',
    loading: q.isLoading,
  }
}
