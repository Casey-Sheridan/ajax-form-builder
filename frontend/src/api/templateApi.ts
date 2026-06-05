export type TemplateDTO = {
  id: string;
  name: string;
  canvas: { width: number; height: number; dpi?: number };
  background: string;
  elements: any[];
};

const API_BASE = "http://localhost:8000";

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
    const res = await fetch(`${API_BASE}/templates/${id}`, {
      method: "DELETE",
    });

    return handle(res);
  },
};