import { renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRevisions } from './useRevisions'
import { networkRevisionApi } from '../../network/networkRevisionApi'
import type { TemplateDTO } from '../../api/templateApi'

// ─── Mocks ───────────────────────────────────────────────────────────────────

vi.mock('../../network/networkRevisionApi', () => ({
  networkRevisionApi: {
    create: vi.fn(),
    createBeacon: vi.fn(),
    list: vi.fn(),
    get: vi.fn(),
  },
}))

const mockCreate = vi.mocked(networkRevisionApi.create)
const mockCreateBeacon = vi.mocked(networkRevisionApi.createBeacon)

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeTemplate(overrides: Partial<TemplateDTO> = {}): TemplateDTO {
  return {
    id: 'tpl-1',
    name: 'Test Template',
    canvas: { width: 1080, height: 1350 },
    background: '',
    elements: [],
    ...overrides,
  }
}

/** Render the hook with a mutable ref so tests can swap the template. */
function renderRevisionsHook(initial: TemplateDTO | null = null) {
  const templateRef = { current: initial }

  const { result, unmount } = renderHook(() => useRevisions(templateRef as any))

  return { result, templateRef, unmount }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('useRevisions', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockCreate.mockResolvedValue({ id: 'rev-1', templateId: 'tpl-1' })
    mockCreateBeacon.mockReturnValue(true)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  // ── seedRevisionHash ────────────────────────────────────────────────────

  describe('seedRevisionHash', () => {
    it('prevents an interval save when template has not changed since seed', async () => {
      const template = makeTemplate()
      const { result, templateRef } = renderRevisionsHook(template)

      act(() => result.current.seedRevisionHash(template))
      templateRef.current = template // still the same object/hash

      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })

      expect(mockCreate).not.toHaveBeenCalled()
    })

    it('resets the baseline so the next interval fires after a change', async () => {
      const original = makeTemplate()
      const { result, templateRef } = renderRevisionsHook(original)

      act(() => result.current.seedRevisionHash(original))

      // Mutate the template (new elements array reference → different JSON)
      templateRef.current = makeTemplate({ elements: [{ id: 'e1', type: 'text',
        field: 'name', label: 'Name', x: 0, y: 0, style: {} } as any] })

      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })

      expect(mockCreate).toHaveBeenCalledOnce()
      expect(mockCreate).toHaveBeenCalledWith('tpl-1', templateRef.current, 'interval')
    })
  })

  // ── Periodic (interval) capture ─────────────────────────────────────────

  describe('periodic interval capture', () => {
    it('fires saveRevisionNow("interval") every 5 minutes', async () => {
      const template = makeTemplate()
      const { templateRef } = renderRevisionsHook(template)
      templateRef.current = template

      // First tick — template not seeded so hash starts as "" → save fires
      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })
      expect(mockCreate).toHaveBeenCalledOnce()

      // Advance another full interval with same template → no change, no save
      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })
      expect(mockCreate).toHaveBeenCalledOnce() // still once

      // Add an element (changes the elements hash) then wait another interval
      templateRef.current = makeTemplate({
        elements: [{ id: 'e1', type: 'text', field: 'f', label: 'L',
                     x: 0, y: 0, style: {} } as any],
      })
      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })
      expect(mockCreate).toHaveBeenCalledTimes(2)
    })

    it('skips the interval save when template ref is null', async () => {
      const { templateRef } = renderRevisionsHook(null)
      templateRef.current = null

      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000)
      })

      expect(mockCreate).not.toHaveBeenCalled()
    })

    it('does not save on interval when hash is unchanged', async () => {
      const template = makeTemplate()
      const { result, templateRef } = renderRevisionsHook(template)

      // Seed so the hash matches the current template
      act(() => result.current.seedRevisionHash(template))
      templateRef.current = template

      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000 * 3) // three ticks
      })

      expect(mockCreate).not.toHaveBeenCalled()
    })

    it('clears the interval on unmount', async () => {
      const template = makeTemplate()
      const { templateRef, unmount } = renderRevisionsHook(template)
      templateRef.current = template

      unmount()

      await act(async () => {
        vi.advanceTimersByTime(5 * 60 * 1000 * 2)
      })

      expect(mockCreate).not.toHaveBeenCalled()
    })
  })

  // ── Event-triggered captures ─────────────────────────────────────────────

  describe('saveRevisionNow — switch trigger', () => {
    it('always saves on "switch" even when hash is unchanged', async () => {
      const template = makeTemplate()
      const { result } = renderRevisionsHook(template)

      // Seed so the hash already matches
      act(() => result.current.seedRevisionHash(template))

      await act(async () => {
        await result.current.saveRevisionNow('switch')
      })

      expect(mockCreate).toHaveBeenCalledOnce()
      expect(mockCreate).toHaveBeenCalledWith('tpl-1', template, 'switch')
    })

    it('saves on "switch" with changed template', async () => {
      const template = makeTemplate({ name: 'Updated' })
      const { result } = renderRevisionsHook(template)

      await act(async () => {
        await result.current.saveRevisionNow('switch')
      })

      expect(mockCreate).toHaveBeenCalledWith('tpl-1', template, 'switch')
    })

    it('is a no-op when templateRef is null', async () => {
      const { result } = renderRevisionsHook(null)

      await act(async () => {
        await result.current.saveRevisionNow('switch')
      })

      expect(mockCreate).not.toHaveBeenCalled()
    })
  })

  describe('saveRevisionNow — manual trigger', () => {
    it('always saves regardless of hash', async () => {
      const template = makeTemplate()
      const { result } = renderRevisionsHook(template)

      act(() => result.current.seedRevisionHash(template))

      await act(async () => {
        await result.current.saveRevisionNow('manual')
      })

      expect(mockCreate).toHaveBeenCalledOnce()
      expect(mockCreate).toHaveBeenCalledWith('tpl-1', template, 'manual')
    })
  })

  // ── beforeunload / unload beacon ─────────────────────────────────────────

  describe('beforeunload beacon capture', () => {
    it('calls createBeacon when template has unsaved changes', () => {
      const template = makeTemplate()
      // Do NOT seed — lastHash stays "", so any template counts as changed
      renderRevisionsHook(template)

      act(() => {
        window.dispatchEvent(new Event('beforeunload'))
      })

      expect(mockCreateBeacon).toHaveBeenCalledOnce()
      expect(mockCreateBeacon).toHaveBeenCalledWith('tpl-1', template)
    })

    it('skips createBeacon when template is unchanged since last save', async () => {
      const template = makeTemplate()
      const { result } = renderRevisionsHook(template)

      // Seed to mark template as "already saved"
      act(() => result.current.seedRevisionHash(template))

      act(() => {
        window.dispatchEvent(new Event('beforeunload'))
      })

      expect(mockCreateBeacon).not.toHaveBeenCalled()
    })

    it('skips createBeacon when templateRef is null', () => {
      renderRevisionsHook(null)

      act(() => {
        window.dispatchEvent(new Event('beforeunload'))
      })

      expect(mockCreateBeacon).not.toHaveBeenCalled()
    })

    it('calls createBeacon after a switch save updates the hash, then more changes occur', async () => {
      const template = makeTemplate()
      const { result, templateRef } = renderRevisionsHook(template)

      // Switch save — captures current hash
      await act(async () => {
        await result.current.saveRevisionNow('switch')
      })
      mockCreate.mockClear()

      // User makes more changes (must touch elements, which is what gets hashed)
      templateRef.current = makeTemplate({
        elements: [{ id: 'e1', type: 'text', field: 'f', label: 'L',
                     x: 0, y: 0, style: {} } as any],
      })

      act(() => {
        window.dispatchEvent(new Event('beforeunload'))
      })

      expect(mockCreateBeacon).toHaveBeenCalledOnce()
    })

    it('removes the beforeunload listener on unmount', () => {
      const template = makeTemplate()
      const { unmount } = renderRevisionsHook(template)

      unmount()

      act(() => {
        window.dispatchEvent(new Event('beforeunload'))
      })

      expect(mockCreateBeacon).not.toHaveBeenCalled()
    })
  })

  // ── Error resilience ────────────────────────────────────────────────────

  describe('error resilience', () => {
    it('rolls back hash on interval save failure so next interval retries', async () => {
      const template = makeTemplate()
      const { result, templateRef } = renderRevisionsHook(template)

      mockCreate.mockRejectedValueOnce(new Error('network error'))

      // First interval — save fails
      await act(async () => {
        await result.current.saveRevisionNow('interval')
      })
      expect(mockCreate).toHaveBeenCalledOnce()

      // Second call — hash was rolled back to "" so it tries again
      mockCreate.mockResolvedValueOnce({ id: 'rev-2', templateId: 'tpl-1' })
      templateRef.current = template

      await act(async () => {
        await result.current.saveRevisionNow('interval')
      })
      expect(mockCreate).toHaveBeenCalledTimes(2)
    })

    it('does not throw to the caller on save failure', async () => {
      const template = makeTemplate()
      const { result } = renderRevisionsHook(template)

      mockCreate.mockRejectedValueOnce(new Error('server error'))

      await expect(
        act(async () => {
          await result.current.saveRevisionNow('interval')
        })
      ).resolves.not.toThrow()
    })

    it('retains hash on non-interval trigger failure (no retry needed)', async () => {
      const template = makeTemplate()
      const { result } = renderRevisionsHook(template)

      mockCreate.mockRejectedValueOnce(new Error('server error'))

      await act(async () => {
        await result.current.saveRevisionNow('switch')
      })

      // After a switch failure the hash is kept (not rolled back to ""),
      // so a subsequent same-hash interval does NOT re-fire.
      mockCreate.mockResolvedValueOnce({ id: 'rev-3', templateId: 'tpl-1' })
      await act(async () => {
        await result.current.saveRevisionNow('interval')
      })

      // The interval call should be skipped because hash still matches
      expect(mockCreate).toHaveBeenCalledOnce() // only the original switch attempt
    })
  })
})
