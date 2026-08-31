import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { canAnalyse, checkService, nextCheckDelay, READY_PATH } from '../serviceStatus'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function answering(status: number) {
  fetchMock.mockResolvedValue({ ok: status < 400, status } as unknown as Response)
}

describe('checkService', () => {
  it('reads a 200 as a service that can analyse', async () => {
    answering(200)

    await expect(checkService('http://localhost:8000')).resolves.toBe('ready')
  })

  it('reads the refusal sent while the model is not in memory as unavailable', async () => {
    answering(503)

    await expect(checkService('http://localhost:8000')).resolves.toBe('unavailable')
  })

  it('reads a deployment that does not route the check as unreachable, not refused', async () => {
    // A 404 is a probe this client cannot interpret, not a service that has
    // said no. Calling it `unavailable` would disable an analysis path that
    // may well work - see `canAnalyse`.
    answering(404)

    await expect(checkService('http://localhost:8000')).resolves.toBe('unreachable')
  })

  it('reads a request that never arrived as unreachable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(checkService('http://localhost:8000')).resolves.toBe('unreachable')
  })

  it('gives up on a check that never settles', async () => {
    // The poll schedules its next run only once this resolves. Without the
    // deadline one hung request stops the loop for good, freezing whatever was
    // on screen - and if that is the warning, nothing but a reload clears it.
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError'))
          )
        })
    )

    const settled = checkService('http://localhost:8000')
    await vi.advanceTimersByTimeAsync(30_000)

    await expect(settled).resolves.toBe('unreachable')
  })

  it('bounds the deadline below the polling interval so two checks never overlap', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError'))
          )
        })
    )

    const settled = checkService('http://localhost:8000')
    await vi.advanceTimersByTimeAsync(nextCheckDelay('unavailable'))

    // Already given up by the time the next check would have been scheduled.
    await expect(settled).resolves.toBe('unreachable')
  })

  it('asks the readiness endpoint and nothing else', async () => {
    answering(200)

    await checkService('http://localhost:8000')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`http://localhost:8000${READY_PATH}`)
    expect(init.method).toBe('GET')
    // No documents, no body: the check is issued before the clinician has
    // selected anything and must never carry content.
    expect(init.body).toBeUndefined()
  })

  it('never reads the answer from a cache', async () => {
    // The value flips underneath the client by design. A cached 503 would leave
    // the warning up for a service that came ready seconds later.
    answering(200)

    await checkService('http://localhost:8000')

    expect(fetchMock.mock.calls[0][1].cache).toBe('no-store')
  })

  it('reports an aborted check without throwing', async () => {
    const controller = new AbortController()
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError'))
          )
        })
    )

    const settled = checkService('http://localhost:8000', controller.signal)
    controller.abort()

    await expect(settled).resolves.toBe('unreachable')
  })

  it('stops the request in flight when the caller gives up on it', async () => {
    // The signal handed to fetch is a composed one, not the caller's own, so
    // this pins that the caller's abort still reaches the open request. It is
    // asserted mid-flight on purpose: the listener is released once the check
    // settles, which is what keeps a long-lived caller signal from collecting
    // one listener per poll.
    const controller = new AbortController()
    let passed: AbortSignal | undefined
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          passed = init.signal as AbortSignal
          passed.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError'))
          )
        })
    )

    const settled = checkService('http://localhost:8000', controller.signal)
    expect(passed?.aborted).toBe(false)

    controller.abort()
    expect(passed?.aborted).toBe(true)
    await expect(settled).resolves.toBe('unreachable')
  })
})

describe('canAnalyse', () => {
  it('closes the door only on the service refusing for itself', () => {
    expect(canAnalyse('unavailable')).toBe(false)
  })

  it('leaves a working analysis path alone when the check merely failed', () => {
    // A deployment that does not route /readyz would otherwise have its
    // analysis - which works - permanently disabled by a probe that does not.
    expect(canAnalyse('unreachable')).toBe(true)
  })

  it('does not hold the interface shut before the first answer', () => {
    expect(canAnalyse('unknown')).toBe(true)
    expect(canAnalyse('ready')).toBe(true)
  })
})

describe('nextCheckDelay', () => {
  it('asks again sooner while the service is down than while it is up', () => {
    // The clinician is waiting out the down state, so it is the one worth
    // polling briskly; a ready service only has to be noticed going away.
    expect(nextCheckDelay('unavailable')).toBeLessThan(nextCheckDelay('ready'))
    expect(nextCheckDelay('unreachable')).toBeLessThan(nextCheckDelay('ready'))
  })

  it('treats the state before the first answer like a down one', () => {
    expect(nextCheckDelay('unknown')).toBe(nextCheckDelay('unavailable'))
  })

  it('never polls in a tight loop', () => {
    for (const status of ['unknown', 'ready', 'unavailable', 'unreachable'] as const) {
      expect(nextCheckDelay(status)).toBeGreaterThanOrEqual(1_000)
    }
  })
})
