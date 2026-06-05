import { apiClient } from "./apiClient";
import type { TemplateDTO } from "../api/templateApi";

export const templateApi = {
  get: (id: string): Promise<TemplateDTO> => {
    console.log("[API GET] template id:", id);
    return apiClient.get<TemplateDTO>(`/templates/${id}`);
  },

  list: (): Promise<TemplateDTO[]> => {
    console.log("[API LIST] templates");
    return apiClient.get<TemplateDTO[]>(`/templates`);
  },

  save: (template: TemplateDTO) => {
    console.log("[API SAVE] template.id:", template?.id);
    console.log("[API SAVE] full payload:", template);

    return apiClient.put(`/templates/${template.id}`, template);
  },

  remove: (id: string) => {
    console.log("[API DELETE] template id:", id);
    return apiClient.delete(`/templates/${id}`);
  },
};
