import { useCallback } from "react";

const SNAP_THRESHOLD = 6;

type Point = { x: number; y: number };

type ElementLike = {
  id: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  size?: number;
  type?: string;
};

/**
 * Extract snap targets from all elements
 */
const getSnapTargets = (elements: ElementLike[]) => {
  const xs: number[] = [];
  const ys: number[] = [];

  for (const el of elements) {
    xs.push(el.x);
    ys.push(el.y);

    if (el.width) xs.push(el.x + el.width);
    if (el.height) ys.push(el.y + el.height);

    if (el.size) {
      xs.push(el.x + el.size / 2);
      ys.push(el.y + el.size / 2);
    }
  }

  return { xs, ys };
};

/**
 * Snap a value to nearest target within threshold
 */
const snapValue = (value: number, targets: number[]) => {
  let closest = value;
  let minDist = SNAP_THRESHOLD;

  for (const t of targets) {
    const dist = Math.abs(value - t);

    if (dist < minDist) {
      minDist = dist;
      closest = t;
    }
  }

  return closest;
};

export function useSnapSystem(elements: ElementLike[]) {
  const snapPoint = useCallback(
    (point: Point): Point => {
      const { xs, ys } = getSnapTargets(elements);

      return {
        x: snapValue(point.x, xs),
        y: snapValue(point.y, ys),
      };
    },
    [elements]
  );

  /**
   * Snap a dragged element's position
   */
  const snapDrag = useCallback(
    (x: number, y: number): Point => {
      return snapPoint({ x, y });
    },
    [snapPoint]
  );

  return {
    snapPoint,
    snapDrag,
  };
}