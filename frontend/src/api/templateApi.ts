export type FieldType =
  | "text"
  | "date"
  | "time"
  | "timeRange"
  | "address"
  | "url"
  | "select"
  | "image";

export type DateFormat = "long" | "long_no_year" | "medium" | "short" | "numeric" | "iso";

export type DerivationStrategy = "asset-lookup" | "fuzzy-catalog" | "format";

export interface FieldDerivation {
  strategy: DerivationStrategy;
  sourceField: string;
  assetType?: string;
  catalog?: string;
  format?: string;
}

export interface FieldDescriptor {
  key: string;
  type: FieldType;
  label: string;
  required?: boolean;
  date_format?: DateFormat;
  placeholder?: string;
  derivation?: FieldDerivation;
  catalog?: string;       // for type="select": names the org-scoped catalog
  allow_custom?: boolean; // enables a free-text "Custom" option
}

export type TemplateDTO = {
  id: string;
  name: string;
  canvas: { width: number; height: number; dpi?: number };
  background: string;
  elements: any[];
  fields: FieldDescriptor[];
};

// A single item returned by GET /catalogs/{name}
export interface CatalogItem {
  id: string;
  value: string;
  label: string;
  image_url: string | null;
  meta: Record<string, unknown>;
  sort_order: number;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function handle(res: Response) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const templateApi = {
  async get(id: string): Promise<TemplateDTO> {
    const res = await fetch(`${API_BASE}/templates/${id}`);
    return handle(res);
  },

  async list(): Promise<TemplateDTO[]> {
    const res = await fetch(`${API_BASE}/templates`);
    return handle(res);
  },

  async save(template: TemplateDTO): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/templates/${template.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(template),
    });
    return handle(res);
  },

  async remove(id: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/templates/${id}`, { method: "DELETE" });
    return handle(res);
  },
};

export const uploadApi = {
  /**
   * Upload any image file for use in the current render session.
   * Returns a URL stored under /static/uploads/ that can be embedded
   * in render data for image fields (e.g. partner_image for a custom partner).
   */
  async uploadTemp(file: File): Promise<{ url: string }> {
    const res = await fetch(`${API_BASE}/uploads/temp`, {
      method: "POST",
      headers: { "x-filename": file.name },
      body: await file.arrayBuffer(),
    });
    return handle(res);
  },
};

export const catalogApi = {
  async list(catalogName: string, orgId?: string): Promise<CatalogItem[]> {
    const params = orgId ? `?org_id=${encodeURIComponent(orgId)}` : "";
    const res = await fetch(`${API_BASE}/catalogs/${catalogName}${params}`);
    const body = await handle(res);
    return body.items as CatalogItem[];
  },

  async addItem(
    catalogName: string,
    item: { value: string; label: string; meta?: Record<string, unknown>; sort_order?: number },
    orgId?: string,
  ): Promise<{ id: string; value: string; label: string }> {
    const params = orgId ? `?org_id=${encodeURIComponent(orgId)}` : "";
    const res = await fetch(`${API_BASE}/catalogs/${catalogName}/items${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item),
    });
    return handle(res);
  },

  async uploadAsset(
    catalogName: string,
    itemId: string,
    file: File,
    orgId?: string,
  ): Promise<{ image_url: string }> {
    const params = orgId ? `?org_id=${encodeURIComponent(orgId)}` : "";
    const res = await fetch(
      `${API_BASE}/catalogs/${catalogName}/items/${itemId}/asset${params}`,
      {
        method: "POST",
        headers: { "x-filename": file.name },
        body: await file.arrayBuffer(),
      },
    );
    return handle(res);
  },

  async removeItem(catalogName: string, itemId: string, orgId?: string): Promise<void> {
    const params = orgId ? `?org_id=${encodeURIComponent(orgId)}` : "";
    await fetch(`${API_BASE}/catalogs/${catalogName}/items/${itemId}${params}`, {
      method: "DELETE",
    });
  },
};