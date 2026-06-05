export type Rect = {
  x: number;
  y: number;
  w: number;
  h: number;
};

export type AlignType =
  | "left"
  | "centerX"
  | "right"
  | "top"
  | "centerY"
  | "bottom";

/**
 * Returns true if two rectangles intersect
 */
export const intersects = (a: Rect, b: Rect): boolean => {
  return !(
    a.x > b.x + b.w ||
    a.x + a.w < b.x ||
    a.y > b.y + b.h ||
    a.y + a.h < b.y
  );
};

/**
 * Get normalized rectangle from marquee drag
 */
export const normalizeRect = (
  x: number,
  y: number,
  w: number,
  h: number
): Rect => {
  return {
    x: Math.min(x, x + w),
    y: Math.min(y, y + h),
    w: Math.abs(w),
    h: Math.abs(h),
  };
};

/**
 * Distance between two points
 */
export const dist = (
  ax: number,
  ay: number,
  bx: number,
  by: number
) => {
  return Math.sqrt((ax - bx) ** 2 + (ay - by) ** 2);
};

/**
 * Snap helper (basic foundation for future expansion)
 */
export const snap = (
  value: number,
  targets: number[],
  threshold: number
): number => {
  let snapped = value;

  for (const t of targets) {
    if (Math.abs(value - t) < threshold) {
      snapped = t;
      break;
    }
  }

  return snapped;
};

/**
 * Get bounding box for an element based on its type and stored dimensions.
 * If actualWidth/actualHeight are provided (e.g. from a Konva node),
 * they take precedence over estimated dimensions.
 */
export function getElementBounds(
  el: any,
  actualWidth?: number,
  actualHeight?: number
): Rect {
  if (el.type === "qr") {
    const s = el.size ?? 120;
    return { x: el.x, y: el.y, w: s, h: s };
  }

  if (el.type === "text") {
    // If a bounding box is set, use its dimensions for alignment purposes
    if (el.boundingBox?.width != null && el.boundingBox?.height != null) {
      return { x: el.x, y: el.y, w: el.boundingBox.width, h: el.boundingBox.height };
    }

    // Use actual node dimensions if available (most accurate)
    if (actualWidth != null && actualHeight != null) {
      return { x: el.x, y: el.y, w: actualWidth, h: actualHeight };
    }
    // Fallback: rough estimate based on font size and text length
    const fontSize = el.style?.size ?? 36;
    const textWidth = (el.label ?? "").length * fontSize * 0.6;
    const textHeight = fontSize * 1.2;
    return { x: el.x, y: el.y, w: textWidth, h: textHeight };
  }

  // Unknown type — use position only with zero size
  return { x: el.x, y: el.y, w: 0, h: 0 };
}

/**
 * Compute new element positions after applying an alignment operation.
 * Returns a map of element id → { x, y } updates.
 */
export function alignElements(
  elements: any[],
  bounds: Rect[],
  type: AlignType
): Record<string, { x: number; y: number }> {
  if (elements.length < 2) return {};

  // Compute the overall bounding box of all selected elements
  const minX = Math.min(...bounds.map((b) => b.x));
  const maxX = Math.max(...bounds.map((b) => b.x + b.w));
  const minY = Math.min(...bounds.map((b) => b.y));
  const maxY = Math.max(...bounds.map((b) => b.y + b.h));
  const centerX = minX + (maxX - minX) / 2;
  const centerY = minY + (maxY - minY) / 2;

  const result: Record<string, { x: number; y: number }> = {};

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    const b = bounds[i];
    let newX = el.x;
    let newY = el.y;

    switch (type) {
      case "left":
        newX = minX;
        break;
      case "centerX":
        newX = centerX - b.w / 2;
        break;
      case "right":
        newX = maxX - b.w;
        break;
      case "top":
        newY = minY;
        break;
      case "centerY":
        newY = centerY - b.h / 2;
        break;
      case "bottom":
        newY = maxY - b.h;
        break;
    }

    // Only store if position changed
    if (newX !== el.x || newY !== el.y) {
      result[el.id] = { x: Math.round(newX), y: Math.round(newY) };
    }
  }

  return result;
}
