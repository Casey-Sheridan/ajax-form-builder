const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Generic key-value map of field data — driven by the template's field descriptors
export type FlyerData = Record<string, string>;

export interface RenderRequest {
  template_id: string;
  data: FlyerData;
}

export async function renderFlyer(
  request: RenderRequest
): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/render/flyer`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP error! status: ${response.status}`);
  }

  return await response.blob();
}