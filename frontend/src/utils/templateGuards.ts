import type { TemplateDTO } from "../api/templateApi";

// ---------------------------
// ELEMENT TYPE GUARDS
// ---------------------------

export function isTextElement(el: any): el is {
  id: string;
  type: "text";
  field: string;
  label: string;
  x: number;
  y: number;
  style: { size: number; color: string };
} {
  return (
    el &&
    el.type === "text" &&
    typeof el.id === "string" &&
    typeof el.label === "string" &&
    typeof el.x === "number" &&
    typeof el.y === "number"
  );
}

export function isQRElement(el: any): el is {
  id: string;
  type: "qr";
  field: string;
  label: string;
  x: number;
  y: number;
  size: number;
} {
  return (
    el &&
    el.type === "qr" &&
    typeof el.id === "string" &&
    typeof el.size === "number"
  );
}

// ---------------------------
// TEMPLATE GUARD
// ---------------------------

export function isValidTemplate(obj: any): obj is TemplateDTO {
  return (
    obj &&
    typeof obj.id === "string" &&
    typeof obj.name === "string" &&
    obj.canvas &&
    typeof obj.canvas.width === "number" &&
    typeof obj.canvas.height === "number" &&
    Array.isArray(obj.elements)
  );
}