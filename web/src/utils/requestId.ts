const REQUEST_ID_STORAGE_KEY = 'requestId'

let fallbackRequestId: string | null = null
const requestIdListeners = new Set<(requestId: string) => void>()

function notifyRequestIdListeners(requestId: string): void {
  requestIdListeners.forEach((listener) => listener(requestId))
}

function createRequestId(): string {
  const webCrypto = globalThis.crypto

  if (typeof webCrypto?.randomUUID === 'function') {
    return webCrypto.randomUUID()
  }

  if (typeof webCrypto?.getRandomValues === 'function') {
    const bytes = webCrypto.getRandomValues(new Uint8Array(16))
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80

    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'))
    return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
  }

  return `request-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export function getOrCreateRequestId(): string {
  try {
    const stored = sessionStorage.getItem(REQUEST_ID_STORAGE_KEY)
    if (stored) {
      fallbackRequestId = stored
      return stored
    }

    const requestId = createRequestId()
    fallbackRequestId = requestId
    sessionStorage.setItem(REQUEST_ID_STORAGE_KEY, requestId)
    return requestId
  } catch {
    fallbackRequestId ??= createRequestId()
    return fallbackRequestId
  }
}

export function resetRequestId(): void {
  fallbackRequestId = null

  try {
    sessionStorage.removeItem(REQUEST_ID_STORAGE_KEY)
  } catch {
    // Ignore unavailable storage; the in-memory fallback was cleared above.
  }
}

export function rotateRequestId(): string {
  resetRequestId()
  const requestId = getOrCreateRequestId()
  notifyRequestIdListeners(requestId)
  return requestId
}

export function subscribeRequestId(listener: (requestId: string) => void): () => void {
  requestIdListeners.add(listener)
  return () => {
    requestIdListeners.delete(listener)
  }
}
