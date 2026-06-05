import { useCallback, useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { TemplateDTO } from "../../api/templateApi";
import { networkRevisionApi } from "../../network/networkRevisionApi";
import type { RevisionTrigger } from "../../network/networkRevisionApi";

// ─── Constants ────────────────────────────────────────────────────────────────

const REVISION_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Produce a change-detection hash for a template by stringifying its elements.
 *
 * We use JSON.stringify rather than a cryptographic hash because:
 *  - Templates are small enough that string comparison is negligible cost
 *  - We need a stable, synchronous value (no async Web Crypto)
 *  - Element objects always serialize in insertion order (V8 guarantee for
 *    non-integer keys), so the same logical state always produces the same string
 */
function hashTemplate(template: TemplateDTO): string {
  return JSON.stringify(template.elements);
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export interface UseRevisionsReturn {
  /**
   * Imperatively save a revision right now.
   *
   * For trigger="interval" the call is a no-op if nothing has changed since the
   * last saved revision (hash unchanged).  All other triggers always persist.
   */
  saveRevisionNow: (trigger: RevisionTrigger) => Promise<void>;

  /**
   * Seed the baseline hash after a template is loaded so the first interval
   * tick doesn't fire spuriously for an unmodified freshly-loaded template.
   *
   * Call this immediately after setTemplate(normalized) inside loadTemplate /
   * the boot effect, passing the just-loaded TemplateDTO directly.
   */
  seedRevisionHash: (template: TemplateDTO) => void;
}

/**
 * useRevisions
 *
 * Manages automatic revision snapshots for the canvas editor.
 *
 * Three save triggers:
 *  1. **interval** — fires every 5 minutes, skipped if elements hash is
 *     unchanged since the last saved revision (no-op on idle sessions).
 *  2. **switch** — called imperatively by useCanvasEngine before it swaps to a
 *     different template, capturing the outgoing state unconditionally.
 *  3. **unload** — registered on window "beforeunload"; uses navigator.sendBeacon
 *     so the request survives the page being torn down.  Skipped if hash is
 *     unchanged (no new work to capture).
 *
 * @param templateRef  A ref that always points at the current TemplateDTO (or
 *                     null).  Using a ref rather than state avoids stale closure
 *                     issues inside the interval callback and the beforeunload
 *                     handler without forcing those effects to re-run on every
 *                     template mutation.
 */
export function useRevisions(
  templateRef: RefObject<TemplateDTO | null>
): UseRevisionsReturn {
  // Hash of the elements at the time of the last saved revision for the
  // currently-loaded template.  Reset to "" when a new template is seeded so
  // the first interval tick correctly detects "no changes yet".
  const lastHashRef = useRef<string>("");

  // ── Core save function ───────────────────────────────────────────────────

  const saveRevisionNow = useCallback(
    async (trigger: RevisionTrigger): Promise<void> => {
      const t = templateRef.current;
      if (!t) return;

      const hash = hashTemplate(t);

      // For interval saves, bail out early if nothing has changed
      if (trigger === "interval" && hash === lastHashRef.current) return;

      // Persist the hash before the await so a rapid double-call (e.g. two
      // concurrent interval ticks) doesn't race and save duplicates.
      lastHashRef.current = hash;

      try {
        await networkRevisionApi.create(t.id, t, trigger);
      } catch (err) {
        // Non-fatal: revision saves are best-effort.  Log and move on so a
        // transient backend hiccup doesn't surface as an error to the user.
        console.warn("[useRevisions] Revision save failed:", err);
        // Roll back the hash so the next interval attempt will retry.
        lastHashRef.current = trigger === "interval" ? "" : hash;
      }
    },
    [templateRef]
  );

  // ── Seed baseline hash after loading a template ──────────────────────────

  const seedRevisionHash = useCallback((template: TemplateDTO): void => {
    lastHashRef.current = hashTemplate(template);
  }, []);

  // ── 5-minute interval ────────────────────────────────────────────────────

  useEffect(() => {
    const id = setInterval(() => {
      saveRevisionNow("interval");
    }, REVISION_INTERVAL_MS);

    return () => clearInterval(id);
  }, [saveRevisionNow]);

  // ── beforeunload beacon ──────────────────────────────────────────────────

  useEffect(() => {
    const handleBeforeUnload = () => {
      const t = templateRef.current;
      if (!t) return;

      const hash = hashTemplate(t);
      if (hash === lastHashRef.current) return; // nothing new to save

      // sendBeacon is fire-and-forget — it queues the request in the browser
      // even after the JS context begins teardown.
      networkRevisionApi.createBeacon(t.id, t);
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [templateRef]);

  return { saveRevisionNow, seedRevisionHash };
}
