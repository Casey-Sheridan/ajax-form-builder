import { apiClient } from "./apiClient";
import type { TemplateDTO } from "../api/templateApi";

const API_BASE = "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export type RevisionTrigger = "interval" | "switch" | "unload" | "manual";

/** Lightweight metadata returned by the list endpoint — no snapshot body. */
export type RevisionMeta = {
  id: string;
  templateId: string;
  trigger: RevisionTrigger;
  createdAt: string;
};

/** Full revision including the template snapshot, returned by the get endpoint. */
export type RevisionDTO = RevisionMeta & {
  snapshot: TemplateDTO;
};

// ─── API ──────────────────────────────────────────────────────────────────────

export const networkRevisionApi = {
  /**
   * Save a revision snapshot for a template.
   * Used for interval, switch, and manual triggers where the page is still open.
   */
  create(
    templateId: string,
    snapshot: TemplateDTO,
    trigger: RevisionTrigger
  ): Promise<{ id: string; templateId: string }> {
    return apiClient.post(`/templates/${templateId}/revisions`, {
      snapshot,
      trigger,
    });
  },

  /**
   * List revision metadata for a template (most-recent first, no snapshot bodies).
   */
  list(templateId: string): Promise<RevisionMeta[]> {
    return apiClient.get(`/templates/${templateId}/revisions`);
  },

  /**
   * Fetch a single revision, including its full snapshot, by ID.
   */
  get(templateId: string, revisionId: string): Promise<RevisionDTO> {
    return apiClient.get(`/templates/${templateId}/revisions/${revisionId}`);
  },

  /**
   * Fire-and-forget revision save via navigator.sendBeacon.
   *
   * sendBeacon is the only reliable mechanism for saving state when the browser
   * tab/window is closing — regular fetch() calls are cancelled before they
   * complete.  The Blob is given Content-Type "application/json" so FastAPI
   * parses it as a normal JSON body.
   *
   * Returns true if the browser accepted the beacon, false otherwise (e.g. if
   * sendBeacon is unavailable or the payload exceeds the browser limit).
   */
  createBeacon(templateId: string, snapshot: TemplateDTO): boolean {
    if (typeof navigator?.sendBeacon !== "function") return false;

    const payload = JSON.stringify({ snapshot, trigger: "unload" });
    const blob = new Blob([payload], { type: "application/json" });
    return navigator.sendBeacon(
      `${API_BASE}/templates/${templateId}/revisions`,
      blob
    );
  },
};
