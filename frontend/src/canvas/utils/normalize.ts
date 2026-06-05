export function normalizeTemplate(data: any) {
  if (!data || typeof data !== "object") {
    throw new Error("[normalizeTemplate] Invalid template payload");
  }

  const bg =
    typeof data.background === "string" &&
    !data.background.includes("undefined")
      ? data.background
      : "";

  // Normalize elements, ensuring text elements have boundingBox/overflow defaults
  const elements = Array.isArray(data.elements)
    ? data.elements.map((el: any) => {
        if (el && el.type === "text") {
          return {
            ...el,
            boundingBox: el.boundingBox ?? null,
            overflow: el.overflow ?? "shrink-to-fit",
          };
        }
        return el;
      })
    : [];

  return {
    id: data.id,
    name: data.name ?? "",
    canvas: data.canvas ?? { width: 1080, height: 1350 },
    background: bg,
    elements,
  };
}
