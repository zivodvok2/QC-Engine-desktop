import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getColumns } from '../api/upload'
import { useAppStore } from '../store/appStore'

export function useColumns() {
  const { fileId, columnNames, setPreview } = useAppStore()

  const query = useQuery({
    queryKey: ['columns', fileId],
    queryFn: () => getColumns(fileId!),
    enabled: !!fileId,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (query.data) {
      setPreview(query.data.sample, query.data.dtypes)
    }
  }, [query.data])

  return {
    columns: columnNames,
    dtypes: query.data?.dtypes ?? {},
    sample: query.data?.sample ?? [],
    isLoading: query.isLoading,
  }
}
