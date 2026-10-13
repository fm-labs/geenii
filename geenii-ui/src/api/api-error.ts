/** Error body of the geenii server (see Problem in src/geenii/datamodels.py) */
export type Problem = {
  error?: string
  status?: number
  detail?: string
}

/** An HTTP error with the server's Problem body ({error, status, detail}). */
export class ApiError extends Error {
  readonly status: number
  readonly response: { status: number; data: unknown }

  constructor(status: number, data: any) {
    super(data?.detail || data?.error || `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    // same shape as axios errors, so errorMessage() finds the Problem detail
    this.response = { status, data }
  }

  get problem(): Problem | null {
    const data = this.response.data
    return data && typeof data === 'object' ? data as Problem : null
  }
}

/** Read the (optional) Problem body of a failed response. */
export const readProblem = async (res: Response): Promise<unknown> => {
  try {
    return await res.json()
  } catch {
    // not a Problem body
    return null
  }
}
