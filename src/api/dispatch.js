const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function fetchPredictedDispatch(signal) {
  const response = await fetch(`${API_BASE_URL}/api/dispatch/predicted`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = `接口请求失败（${response.status}）`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(detail)
  }

  return response.json()
}
