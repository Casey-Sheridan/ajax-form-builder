import { useRef } from "react";

export function useHistory() {
  const stack = useRef<any[]>([]);
  const index = useRef(-1);

  const push = (state: any) => {
    const snapshot = structuredClone(state);

    stack.current = stack.current.slice(0, index.current + 1);
    stack.current.push(snapshot);
    index.current++;
  };

  const undo = () => {
    if (index.current <= 0) return null;
    index.current--;
    return stack.current[index.current];
  };

  const redo = () => {
    if (index.current >= stack.current.length - 1) return null;
    index.current++;
    return stack.current[index.current];
  };

  const reset = (state: any) => {
    const snapshot = structuredClone(state);
    stack.current = [snapshot];
    index.current = 0;
  };

  const clear = () => {
    stack.current = [];
    index.current = -1;
  };

  const getLength = () => stack.current.length;

  return { push, undo, redo, reset, clear, getLength };
}