import { useEffect } from "react";

export function useKeyboardShortcuts({
  undo,
  redo,
  duplicate,
  delete: deleteFn,
  nudgeSelected,
}: {
  undo: () => void;
  redo: () => void;
  duplicate: () => void;
  delete: () => void;
  nudgeSelected: (deltaX: number, deltaY: number) => void;
}) {
  useEffect(() => {
    const isEditableTarget = (target: EventTarget | null) => {
      const el = target as HTMLElement | null;
      const tag = el?.tagName;

      return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        el?.isContentEditable === true
      );
    };

    const handler = (e: KeyboardEvent) => {
      const cmd = e.metaKey || e.ctrlKey;
      const isEditingText = isEditableTarget(e.target);

      if (cmd && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      }

      if (cmd && e.key === "z" && e.shiftKey) {
        e.preventDefault();
        redo();
      }

      if (cmd && e.key.toLowerCase() === "d") {
        e.preventDefault();
        duplicate();
      }

      if (!cmd && !e.altKey && !isEditingText) {
        const arrowDeltas: Record<string, [number, number]> = {
          ArrowUp: [0, -1],
          ArrowDown: [0, 1],
          ArrowLeft: [-1, 0],
          ArrowRight: [1, 0],
        };
        const delta = arrowDeltas[e.key];

        if (delta) {
          e.preventDefault();
          const multiplier = e.shiftKey ? 10 : 1;
          nudgeSelected(delta[0] * multiplier, delta[1] * multiplier);
        }
      }

      // Delete/Backspace — only if not typing in an input
      if ((e.key === "Delete" || e.key === "Backspace") && !cmd) {
        if (!isEditingText) {
          e.preventDefault();
          deleteFn();
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () =>
      window.removeEventListener("keydown", handler);
  }, [undo, redo, duplicate, deleteFn, nudgeSelected]);
}
