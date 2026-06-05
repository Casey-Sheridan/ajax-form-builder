import { useState, useRef, useEffect } from "react";
import { APPROVED_FONTS, DEFAULT_FONT_FAMILY } from "./fonts";

interface Props {
  value: string;
  onChange: (family: string) => void;
}

const BASE_INPUT: React.CSSProperties = {
  width: "100%",
  padding: "6px 8px",
  background: "#222",
  border: "1px solid #333",
  borderRadius: 4,
  color: "#fff",
  fontSize: 13,
  boxSizing: "border-box",
  outline: "none",
};

export function FontSelector({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const current = value || DEFAULT_FONT_FAMILY;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          ...BASE_INPUT,
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 4,
        }}
      >
        <span style={{ fontFamily: current, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {current}
        </span>
        <span style={{ color: "#555", fontSize: 10, flexShrink: 0 }}>▾</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 2px)",
            left: 0,
            right: 0,
            zIndex: 1000,
            background: "#1a1a1a",
            border: "1px solid #444",
            borderRadius: 4,
            maxHeight: 300,
            overflowY: "auto",
            boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
          }}
        >
          {APPROVED_FONTS.map((font) => (
            <FontOption
              key={font.family}
              family={font.family}
              selected={current === font.family}
              onClick={() => { onChange(font.family); setOpen(false); }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FontOption({
  family,
  selected,
  onClick,
}: {
  family: string;
  selected: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: "7px 10px",
        cursor: "pointer",
        fontFamily: family,
        fontSize: 14,
        color: selected ? "#4af" : "#ccc",
        background: selected
          ? "rgba(68,170,255,0.12)"
          : hovered
          ? "#262626"
          : "transparent",
        transition: "background 0.1s",
      }}
    >
      {family}
    </div>
  );
}
