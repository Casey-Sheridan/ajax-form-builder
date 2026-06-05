import { useState } from "react";

type SelectMode = "single" | "toggle" | "replace";

export function useSelection() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // ---------------------------------------------------
  // CORE SET (used by engine, box select, bulk ops)
  // ---------------------------------------------------
  const set = (ids: string[]) => {
    setSelectedIds([...ids]);
  };

  // ---------------------------------------------------
  // FLEXIBLE SELECT (used by CanvasEditor + clicks)
  // ---------------------------------------------------
  const select = (input: string | string[], mode: SelectMode = "single") => {
    const ids = Array.isArray(input) ? input : [input];

    setSelectedIds((prev) => {
      switch (mode) {
        case "replace":
          return ids;

        case "toggle": {
          const set = new Set(prev);
          ids.forEach((id) =>
            set.has(id) ? set.delete(id) : set.add(id)
          );
          return Array.from(set);
        }

        case "single":
        default:
          return ids;
      }
    });
  };

  const isSelected = (id: string) => {
    return selectedIds.includes(id);
  };

  const clear = () => setSelectedIds([]);

  return {
    selectedIds,

    // full compatibility surface
    select,
    set,
    clear,
    isSelected,
  };
}