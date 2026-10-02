import { useCallback, useEffect, useState } from 'react'

import { type ApiClient, ApiError, type DocumentRecord, precheckUpload, uploadErrorReason } from '../api/types'

export interface UploadProgress {
  key: string
  filename: string
  progress: number
}

export interface UploadError {
  key: string
  filename: string
  reason: string
}

export function useDocuments(client: ApiClient) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [uploads, setUploads] = useState<UploadProgress[]>([])
  const [errors, setErrors] = useState<UploadError[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setDocuments(await client.listDocuments())
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not load documents.')
    }
  }, [client])

  useEffect(() => {
    let cancelled = false
    client.listDocuments().then(
      (docs) => !cancelled && setDocuments(docs),
      (e) => !cancelled && setLoadError(e instanceof Error ? e.message : 'Could not load documents.'),
    )
    return () => {
      cancelled = true
    }
  }, [client])

  const addError = (filename: string, reason: string) =>
    setErrors((prev) => [...prev, { key: crypto.randomUUID(), filename, reason }])

  const uploadOne = useCallback(
    async (file: File) => {
      const precheck = precheckUpload(file)
      if (precheck) return addError(file.name, precheck)
      const key = crypto.randomUUID()
      setUploads((prev) => [...prev, { key, filename: file.name, progress: 0 }])
      try {
        const record = await client.uploadDocument(file, (progress) =>
          setUploads((prev) => prev.map((u) => (u.key === key ? { ...u, progress } : u))),
        )
        setDocuments((prev) => [...prev.filter((d) => d.id !== record.id), record])
      } catch (e) {
        addError(file.name, e instanceof ApiError ? uploadErrorReason(e.status, e.message) : String(e))
      } finally {
        setUploads((prev) => prev.filter((u) => u.key !== key))
      }
    },
    [client],
  )

  const upload = useCallback((files: Iterable<File>) => Promise.all([...files].map(uploadOne)), [uploadOne])

  const remove = useCallback(
    async (id: string) => {
      await client.deleteDocument(id)
      setDocuments((prev) => prev.filter((d) => d.id !== id))
    },
    [client],
  )

  const clear = useCallback(async () => {
    await client.clearDocuments()
    setDocuments([])
  }, [client])

  const dismissError = useCallback((key: string) => setErrors((prev) => prev.filter((e) => e.key !== key)), [])

  return { documents, uploads, errors, loadError, upload, remove, clear, dismissError, refresh }
}
