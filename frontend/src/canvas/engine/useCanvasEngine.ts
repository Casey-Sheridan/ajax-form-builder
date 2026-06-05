import { useCallback, useEffect, useRef, useState } from "react";

import type { TemplateDTO, FieldDescriptor } from "../../api/templateApi";
import { templateApi } from "../../network/networkTemplateApi";
import { requestQueue } from "../../network/requestQueue";

import { useHistory } from "../hooks/useHistory";
import { useSelection } from "../hooks/useSelection";
import { useSnapSystem } from "../hooks/useSnapSystem";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useRevisions } from "../hooks/useRevisions";

import { isValidTemplate } from "../utils/validation";
import { normalizeTemplate } from "../utils/normalize";

const AUTOSAVE_DELAY = 600;
const API_BASE = "http://localhost:8000";
const LAST_TEMPLATE_KEY = "canvasEditor:lastTemplateId";
// Cleared when the browser tab closes; used to distinguish same-session
// navigation (restore last template) from a fresh page load (show empty workspace).
const SESSION_ACTIVE_KEY = "canvasEditor:sessionActive";

export function useCanvasEngine() {
  // =====================================================
  // STATE
  // =====================================================
  const [template, setTemplate] = useState<TemplateDTO | null>(null);
  const [templates, setTemplates] = useState<TemplateDTO[]>([]);
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const [isBooting, setIsBooting] = useState(true);

  // =====================================================
  // KONVA STABILITY LAYER
  // =====================================================
  const stageRef = useRef<any>(null);
  const renderLock = useRef(false);

  // =====================================================
  // TEMPLATE REF  (always current — updated every render)
  // Used by useRevisions and by loadTemplate (which intentionally
  // has a narrow dep array) so they never hold stale template state.
  // =====================================================
  const templateRef = useRef<TemplateDTO | null>(null);
  templateRef.current = template;

  // =====================================================
  // REVISION CALLBACK BRIDGES
  // Stable ref wrappers so loadTemplate's eslint-disable dep exemption
  // remains valid — we never need to add revision callbacks to its dep array.
  // =====================================================
  const saveRevisionNowRef = useRef<
    ((trigger: "interval" | "switch" | "unload" | "manual") => Promise<void>) | null
  >(null);
  const seedRevisionHashRef = useRef<((t: TemplateDTO) => void) | null>(null);

  // =====================================================
  // SYSTEMS
  // =====================================================
  const history = useHistory();
  const selection = useSelection();
  const snap = useSnapSystem(template?.elements ?? []);

  // =====================================================
  // REVISIONS
  // Wire up after templateRef is defined. Update the bridge refs every render
  // so loadTemplate's closure always calls the latest callbacks.
  // =====================================================
  const { saveRevisionNow, seedRevisionHash } = useRevisions(templateRef);
  saveRevisionNowRef.current = saveRevisionNow;
  seedRevisionHashRef.current = seedRevisionHash;

  const resetHistory = useCallback(
    (initialState?: TemplateDTO) => {
      const anyHistory = history as any;

      if (typeof anyHistory.clear === "function") {
        anyHistory.clear();
      } else if (typeof anyHistory.reset === "function") {
        anyHistory.reset(initialState);
      }

      if (initialState) {
        history.push(structuredClone(initialState));
      }
    },
    [history]
  );

  // =====================================================
  // SAFETY / LIFECYCLE FLAGS
  // =====================================================
  const didLoad = useRef(false);
  const isHydrated = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastCommit = useRef(0);

  // =====================================================
  // SAFE SAVE QUEUE
  // =====================================================
  const save = useCallback(async (t: TemplateDTO) => {
    requestQueue.enqueue(async () => {
      try {
        const safeT = structuredClone(t);
        await templateApi.save(safeT);
      } catch (err) {
        console.error("Save failed:", err);
      }
    });
  }, []);

  // =====================================================
  // AUTOSAVE (HYDRATION-GATED)
  // =====================================================
  const scheduleSave = useCallback(
    (t: TemplateDTO) => {
      if (!isHydrated.current) return;

      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
      }

      saveTimer.current = setTimeout(() => {
        save(t);
      }, AUTOSAVE_DELAY);
    },
    [save]
  );

  // =====================================================
  // COMMIT (RATE LIMITED)
  // =====================================================
  const commit = useCallback(
    (next: TemplateDTO) => {
      const now = Date.now();

      if (now - lastCommit.current < 250) return;

      lastCommit.current = now;

      if (!isValidTemplate(next)) {
        console.error("[ENGINE COMMIT] Invalid template blocked:", next);
        return;
      }

      const safeNext = structuredClone(next);

      console.log("[ENGINE STATE SNAPSHOT]", structuredClone(next));
      console.trace();
      setTemplate(safeNext);
      history.push(safeNext);
      scheduleSave(safeNext);
    },
    [history, scheduleSave]
  );

  // =====================================================
  // LOCAL UPDATE (NO NETWORK)
  // =====================================================
  const updateElementLocal = useCallback(
    (id: string, updates: any) => {
      setTemplate((prev) => {
        if (!prev) return prev;

        return {
          ...prev,
          elements: prev.elements.map((el) =>
            el.id === id ? { ...el, ...updates } : el
          ),
        };
      });
    },
    []
  );

  // =====================================================
  // UPDATE FIELD DESCRIPTOR (template-level, not element-level)
  // Multiple elements can share a field key — this edits the one descriptor
  // for that key, or inserts a new one if it doesn't exist yet.
  // =====================================================
  const updateFieldDescriptor = useCallback(
    (key: string, patch: Partial<FieldDescriptor>) => {
      setTemplate((prev) => {
        if (!prev) return prev;
        const exists = prev.fields.some((d) => d.key === key);
        const fields = exists
          ? prev.fields.map((d) => (d.key === key ? { ...d, ...patch } : d))
          : [...prev.fields, { key, type: "text" as const, label: key, required: true, ...patch }];
        return { ...prev, fields };
      });
    },
    []
  );

  // =====================================================
  // COMMIT UPDATE (WITH SNAP)
  // =====================================================
  const updateElement = useCallback(
    (id: string, updates: any) => {
      if (!template) return;

      const next: TemplateDTO = {
        ...template,
        elements: template.elements.map((el: any) => {
          if (el.id !== id) return el;

          const snapped =
            updates.x != null || updates.y != null
              ? snap.snapDrag(updates.x ?? el.x, updates.y ?? el.y)
              : null;

          return {
            ...el,
            ...updates,
            x: snapped?.x ?? el.x,
            y: snapped?.y ?? el.y,
          };
        }),
      };

      const safeNext = structuredClone(next);

      console.log("[ENGINE STATE SNAPSHOT]", structuredClone(next));
      console.trace();

      commit(safeNext);
    },
    [template, commit, snap]
  );

  // =====================================================
  // REFRESH TEMPLATE LIST
  // =====================================================
  const refreshTemplateList = useCallback(async () => {
    try {
      const list = await templateApi.list();
      setTemplates(list);
    } catch (err) {
      console.error("[ENGINE] Template list fetch failed:", err);
    }
  }, []);

  // =====================================================
  // LOAD TEMPLATE BY ID
  //
  // Revision behaviour:
  //   • Before switching away from an open template, save a 'switch' revision
  //     unconditionally — this captures the last known state of the outgoing
  //     template regardless of the 5-minute interval.
  //   • After the new template is fully loaded, seed the revision hash baseline
  //     so the interval won't fire a spurious save for an unmodified template.
  //
  // Note: saveRevisionNowRef / seedRevisionHashRef are used (not the callbacks
  // directly) so this function's intentionally-narrow dep array remains valid.
  // =====================================================
  const loadTemplate = useCallback(
    async (id: string) => {
      // Gate: don't re-load the same template that's already active
      if (templateRef.current?.id === id) return;

      // ── Save a revision of the outgoing template before switching ──────────
      if (templateRef.current) {
        // Fire-and-don't-await: we don't want a slow network call to block the
        // UX of switching templates.  The revision is best-effort.
        saveRevisionNowRef.current?.("switch").catch((err) => {
          console.warn("[ENGINE LOAD] Pre-switch revision save failed:", err);
        });
      }

      isHydrated.current = false;

      try {
        console.log("[ENGINE LOAD] template", id);
        const data = await templateApi.get(id);

        if (!isValidTemplate(data)) {
          console.error("[ENGINE LOAD] Invalid template:", data);
          return;
        }

        const normalized = normalizeTemplate(data);

        console.log("[ENGINE STATE SNAPSHOT]", structuredClone(normalized));
        console.trace();

        setTemplate(normalized);

        // Keep templateRef in sync within the async context so seedRevisionHash
        // reads the correct template without waiting for a re-render.
        templateRef.current = normalized;
        seedRevisionHashRef.current?.(normalized);

        resetHistory(normalized);
        selection.clear();
        setBgImage(null);

        isHydrated.current = true;

        try {
          localStorage.setItem(LAST_TEMPLATE_KEY, id);
          sessionStorage.setItem(SESSION_ACTIVE_KEY, "1");
        } catch (_) {
          // ignore storage errors in restricted contexts
        }
      } catch (err) {
        console.error("[ENGINE LOAD] Template load failed:", err);
      }
    },
    // Intentionally exclude `template` from deps — we only need the id comparison
    // at the moment of the call, not a stale-closure re-create on every render.
    // templateRef / saveRevisionNowRef / seedRevisionHashRef are refs (stable),
    // so they also don't need to be in the dep array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [history, selection, resetHistory]
  );

  // =====================================================
  // CREATE TEMPLATE
  // =====================================================
  const createTemplate = useCallback(
    async (name: string, width: number, height: number, background = "", dpi = 72) => {
      const newTemplate: TemplateDTO = {
        id: crypto.randomUUID(),
        name,
        canvas: { width, height, dpi },
        background,
        elements: [],
      };

      try {
        console.log("[ENGINE CREATE] template", newTemplate.id, name);
        await templateApi.save(newTemplate);

        setTemplates((prev) => [...prev, newTemplate]);

        await loadTemplate(newTemplate.id);

        await refreshTemplateList();
      } catch (err) {
        console.error("[ENGINE CREATE] Failed:", err);
        setTemplates((prev) => prev.filter((t) => t.id !== newTemplate.id));
      }
    },
    [loadTemplate, refreshTemplateList]
  );

  // =====================================================
  // DELETE TEMPLATE
  // =====================================================
  const deleteTemplate = useCallback(
    async (id: string) => {
      try {
        await templateApi.remove(id);
        const remaining = await templateApi.list();
        setTemplates(remaining);
        if (templateRef.current?.id === id) {
          setTemplate(null);
        }
      } catch (err) {
        console.error("[ENGINE DELETE] Failed:", err);
      }
    },
    []
  );

  // =====================================================
  // INITIAL LOAD
  // =====================================================
  useEffect(() => {
    if (didLoad.current) return;
    didLoad.current = true;

    const boot = async () => {
      try {
        const list = await templateApi.list();
        setTemplates(list);

        // Restore the last working copy only when navigating back within the same
        // browser session. SESSION_ACTIVE_KEY is sessionStorage so it clears on
        // tab close, giving a clean workspace on a fresh page load.
        const isReturningVisit = !!sessionStorage.getItem(SESSION_ACTIVE_KEY);
        const lastId = localStorage.getItem(LAST_TEMPLATE_KEY);
        if (isReturningVisit && lastId && list.some((t) => t.id === lastId)) {
          await loadTemplate(lastId);
        }
      } catch (err) {
        console.error("[ENGINE BOOT] Failed:", err);
      } finally {
        setIsBooting(false);
      }
    };

    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // =====================================================
  // BACKGROUND IMAGE (SAFE + CANCELABLE)
  // =====================================================
  useEffect(() => {
    const bg = template?.background;

    if (!bg || typeof bg !== "string") return;

    if (bg.includes("test_event") || bg.includes("undefined")) {
      console.error("[ENGINE BG BLOCKED INVALID VALUE]", bg);
      return;
    }

    let cancelled = false;

    const img = new Image();
    img.crossOrigin = "Anonymous";
    img.src = `${API_BASE}${bg}`;

    img.onload = () => {
      if (cancelled) return;
      setBgImage(img);
    };

    img.onerror = (e) => {
      console.error("Background image failed:", e);
    };

    return () => {
      cancelled = true;
    };
  }, [template?.background]);

  // =====================================================
  // KONVA RENDER ISOLATION
  // =====================================================
  const requestRender = useCallback(() => {
    if (!stageRef.current) return;
    if (renderLock.current) return;

    renderLock.current = true;

    requestAnimationFrame(() => {
      stageRef.current?.batchDraw?.();
      renderLock.current = false;
    });
  }, []);

  // =====================================================
  // BATCH UPDATE ELEMENTS (for alignment, etc.)
  // =====================================================
  const updateElements = useCallback(
    (elementUpdates: Record<string, any>) => {
      if (!template) return;

      const next: TemplateDTO = {
        ...template,
        elements: template.elements.map((el: any) => {
          const updates = elementUpdates[el.id];
          return updates ? { ...el, ...updates } : el;
        }),
      };

      commit(next);
    },
    [template, commit]
  );

  // =====================================================
  // ADD ELEMENT
  // =====================================================
  const addElement = useCallback(
    (element: any) => {
      if (!template) return;

      console.log("[ENGINE ADD ELEMENT]", element);

      const next: TemplateDTO = {
        ...template,
        elements: [...template.elements, element],
      };

      commit(next);
      selection.set([element.id]);
    },
    [template, commit, selection]
  );

  // =====================================================
  // DELETE SELECTED ELEMENTS
  // =====================================================
  const deleteSelected = useCallback(() => {
    if (!template) return;

    const ids = selection.selectedIds;
    if (ids.length === 0) return;

    console.log("[ENGINE DELETE ELEMENTS]", ids);

    const next: TemplateDTO = {
      ...template,
      elements: template.elements.filter(
        (el: any) => !ids.includes(el.id)
      ),
    };

    commit(next);
    selection.clear();
  }, [template, commit, selection]);

  // =====================================================
  // NUDGE SELECTED ELEMENTS
  // =====================================================
  const nudgeSelected = useCallback(
    (deltaX: number, deltaY: number) => {
      const ids = selection.selectedIds;
      if (ids.length === 0) return;

      setTemplate((prev) => {
        if (!prev) return prev;

        const next: TemplateDTO = {
          ...prev,
          elements: prev.elements.map((el: any) =>
            ids.includes(el.id)
              ? { ...el, x: el.x + deltaX, y: el.y + deltaY }
              : el
          ),
        };

        if (!isValidTemplate(next)) {
          console.error("[ENGINE NUDGE] Invalid template blocked:", next);
          return prev;
        }

        const safeNext = structuredClone(next);
        history.push(safeNext);
        scheduleSave(safeNext);

        return safeNext;
      });
    },
    [history, scheduleSave, selection.selectedIds]
  );

  // =====================================================
  // KEYBOARD SHORTCUTS
  // =====================================================
  useKeyboardShortcuts({
    undo: () => {
      const prev = history.undo();
      if (prev) setTemplate(prev);
    },

    redo: () => {
      const next = history.redo();
      if (next) setTemplate(next);
    },

    duplicate: () => {
      if (!template) return;

      const clones = template.elements
        .filter((el: any) => selection.selectedIds.includes(el.id))
        .map((el: any) => ({
          ...el,
          id: crypto.randomUUID(),
          x: el.x + 20,
          y: el.y + 20,
        }));

      const next = {
        ...template,
        elements: [...template.elements, ...clones],
      };

      console.log("[ENGINE STATE SNAPSHOT]", structuredClone(next));
      console.trace();
      commit(next);
      selection.set(clones.map((c) => c.id));
    },

    delete: deleteSelected,

    nudgeSelected,
  });

  // =====================================================
  // API
  // =====================================================
  return {
    template,
    templates,
    bgImage,
    isBooting,

    stageRef,
    requestRender,

    history,
    selection,
    snap,

    updateElements,
    updateElement,
    updateElementLocal,
    updateFieldDescriptor,
    commit,

    addElement,
    deleteSelected,
    loadTemplate,
    createTemplate,
    deleteTemplate,

    saveRevisionNow,
  };
}
