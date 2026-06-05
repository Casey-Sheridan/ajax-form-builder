import { useCallback, useState } from "react";
import type { TemplateDTO } from "../../api/templateApi";

export function useCanvasElements(
  template: TemplateDTO | null,
  setTemplate: (t: TemplateDTO) => void,
  pushHistory: (t: TemplateDTO) => void,
  save: (t: TemplateDTO) => void
) {
  const [isDirty, setIsDirty] = useState(false);

  const updateTemplate = useCallback(
    (next: TemplateDTO) => {
      setTemplate(next);
      pushHistory(next);
      save(next);
      setIsDirty(true);
    },
    [setTemplate, pushHistory, save]
  );

  const updateElement = useCallback(
    (id: string, updates: any) => {
      if (!template) return;

      const next: TemplateDTO = {
        ...template,
        elements: template.elements.map((el: any) => {
          if (el.id !== id) return el;

          if (el.type === "text") {
            return {
              ...el,
              x: updates.x ?? el.x,
              y: updates.y ?? el.y,
              label: updates.label ?? el.label,
              style: { ...el.style, ...updates.style },
            };
          }

          if (el.type === "qr") {
            return {
              ...el,
              x: updates.x ?? el.x,
              y: updates.y ?? el.y,
              size: updates.size ?? el.size,
            };
          }

          return el;
        }),
      };

      updateTemplate(next);
    },
    [template, updateTemplate]
  );

  return {
    updateTemplate,
    updateElement,
    isDirty,
    setIsDirty,
  };
}