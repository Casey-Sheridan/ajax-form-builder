import type { TemplateDTO } from "../../api/templateApi";

export function isValidTemplate(t: any): t is TemplateDTO {
  if (!t) return false;

  // -----------------------------
  // STRUCTURE CHECK (FAST FAIL)
  // -----------------------------
  if (typeof t.id !== "string") return false;
  if (!Array.isArray(t.elements)) return false;
  if (!t.canvas || typeof t.canvas !== "object") return false;

  // -----------------------------
  // DOMAIN RULES (REAL VALIDATION)
  // -----------------------------
   for (const el of t.elements) {
     if (!el.id || typeof el.id !== "string") return false;

     if (typeof el.x !== "number" || typeof el.y !== "number") {
       return false;
     }

     if (el.type === "image" && typeof el.label !== "string") {
       return false;
     }

     if (el.type === "text" && typeof el.label !== "string") {
       return false;
     }

     if (el.type === "qr" && typeof el.label !== "string") {
       return false;
     }
   }

  // -----------------------------
  // CANVAS RULES
  // -----------------------------
  if (
    typeof t.canvas.width !== "number" ||
    typeof t.canvas.height !== "number"
  ) {
    return false;
  }

  return true;
}