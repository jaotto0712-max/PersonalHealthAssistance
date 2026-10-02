import { httpClient } from './http'
import { createMockClient } from './mock'
import type { ApiClient } from './types'

export const isMockApi = import.meta.env.VITE_MOCK_API === 'true'

/** The API used by the app: the real backend, or the in-memory mock when VITE_MOCK_API=true. */
export const api: ApiClient = isMockApi ? createMockClient() : httpClient

export * from './types'
