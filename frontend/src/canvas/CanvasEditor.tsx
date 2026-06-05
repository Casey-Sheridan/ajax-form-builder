import {
  Stage,
  Layer,
  Rect,
  Text,
  Transformer,
  Image as KonvaImage,
  Group,
} from "react-konva";

import Konva from "konva";
import { useRef, useState, useEffect, useCallback } from "react";

import { useCanvasEngine } from "./engine/useCanvasEngine";
import type { AlignType } from "./utils/canvasMath";
import { alignElements, getElementBounds } from "./utils/canvasMath";
import { FontSelector } from "./FontSelector";
import {
  GOOGLE_LOADABLE_FONTS,
  BACKEND_FONTS,
  DEFAULT_FONT_FAMILY,
  buildGoogleFontsUrl,
} from "./fonts";

// ─── constants ────────────────────────────────────────────────────────────────
import type { TemplateDTO } from "../api/templateApi";

const QR_PREVIEW_TEXT = "Hello, world!";
const API_BASE = "http://localhost:8000";

async function uploadBackgroundImage(file: File): Promise<string> {
  const res = await fetch(`${API_BASE}/backgrounds`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Filename": file.name,
    },
    body: file,
  });

  if (!res.ok) {
    throw new Error(await res.text() || `Background upload failed: HTTP ${res.status}`);
  }

  const data = await res.json();
  return data.path;
}

// ─── NEW TEMPLATE DIALOG ──────────────────────────────────────────────────────
function NewTemplateDialog({
  onConfirm,
  onCancel,
}: {
  onConfirm: (name: string, width: number, height: number, backgroundImage?: File | null, dpi?: number) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("Untitled Template");
  const [width, setWidth] = useState(800);
  const [height, setHeight] = useState(600);
  const [dpi, setDpi] = useState(72);
  const [backgroundImage, setBackgroundImage] = useState<File | null>(null);

  const presets = [
    { label: "A4 Portrait (300 DPI)", w: 2480, h: 3508, dpi: 300 },
    { label: "A4 Landscape (300 DPI)", w: 3508, h: 2480, dpi: 300 },
    { label: "US Letter (300 DPI)", w: 2550, h: 3300, dpi: 300 },
    { label: "US Letter (400 DPI)", w: 3400, h: 4400, dpi: 400 },
    { label: "Square 300 DPI", w: 2400, h: 2400, dpi: 300 },
    { label: "Banner 16:9 HD", w: 1920, h: 1080, dpi: 96 },
    { label: "Banner 16:9 Print", w: 3840, h: 2160, dpi: 96 },
  ];

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: "#161616",
          border: "1px solid #2a2a2a",
          borderRadius: 10,
          padding: 28,
          width: 380,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ margin: 0, color: "#fff", fontSize: 16, fontWeight: 600 }}>
          New Template
        </h2>

        {/* Name */}
        <div>
          <label style={labelStyle}>Template Name</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
            placeholder="e.g. Event Badge"
          />
        </div>

        {/* Presets */}
        <div>
          <label style={labelStyle}>Size Preset</label>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {presets.map((p) => (
              <button
                key={p.label}
                onClick={() => {
                  setWidth(p.w);
                  setHeight(p.h);
                  setDpi(p.dpi);
                }}
                style={{
                  padding: "4px 10px",
                  background: width === p.w && height === p.h ? "#3a6bff" : "#252525",
                  border: "1px solid #333",
                  borderRadius: 4,
                  color: "#ccc",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Dimensions */}
        <div style={{ display: "flex", gap: 10 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Width (px)</label>
            <input
              type="number"
              value={width}
              onChange={(e) => setWidth(parseInt(e.target.value) || 100)}
              style={inputStyle}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Height (px)</label>
            <input
              type="number"
              value={height}
              onChange={(e) => setHeight(parseInt(e.target.value) || 100)}
              style={inputStyle}
            />
          </div>
        </div>

        <div>
          <label style={labelStyle}>Background Image (optional)</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              setBackgroundImage(file);
            }}
            style={{ color: "#ccc", fontSize: 12 }}
          />
          {backgroundImage && (
            <div style={{ marginTop: 6, color: "#777", fontSize: 11 }}>
              {backgroundImage.name}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 4 }}>
          <button onClick={onCancel} style={cancelBtnStyle}>
            Cancel
          </button>
          <button
            onClick={() =>
              name.trim() && onConfirm(name.trim(), width, height, backgroundImage, dpi)
            }
            style={primaryBtnStyle}
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── TEMPLATE PICKER PANEL ────────────────────────────────────────────────────
function TemplatePicker({
  templates,
  currentId,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: {
  templates: TemplateDTO[];
  currentId: string | undefined;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const confirmTemplate = confirmId ? templates.find((t) => t.id === confirmId) : null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        zIndex: 900,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: 56,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#161616",
          border: "1px solid #2a2a2a",
          borderRadius: 10,
          width: 560,
          maxHeight: "70vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid #222",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ color: "#fff", fontWeight: 600, fontSize: 14 }}>
            Templates
          </span>
          <button
            onClick={onNew}
            style={{
              ...primaryBtnStyle,
              padding: "5px 14px",
              fontSize: 12,
            }}
          >
            + New Template
          </button>
        </div>

        {/* List */}
        <div style={{ overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          {templates.length === 0 && (
            <div style={{ color: "#555", fontSize: 13, padding: "20px 0", textAlign: "center" }}>
              No templates yet. Create one to get started.
            </div>
          )}
          {templates.map((t) => (
            <div
              key={t.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: 7,
                background: t.id === currentId ? "#1e2f5a" : "#1c1c1c",
                border: `1px solid ${t.id === currentId ? "#3a6bff" : "#282828"}`,
                transition: "background 0.1s",
              }}
            >
              {/* Mini canvas swatch */}
              <div
                onClick={() => onSelect(t.id)}
                style={{
                  width: 48,
                  height: 36,
                  background: "#2a2a2a",
                  borderRadius: 4,
                  border: "1px solid #333",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  fontSize: 9,
                  color: "#555",
                  cursor: "pointer",
                }}
              >
                {t.canvas ? `${t.canvas.width}×${t.canvas.height}` : "—"}
              </div>

              <div onClick={() => onSelect(t.id)} style={{ flex: 1, minWidth: 0, cursor: "pointer" }}>
                <div
                  style={{
                    color: "#eee",
                    fontSize: 13,
                    fontWeight: 500,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t.name}
                </div>
              </div>

              {t.id === currentId && (
                <span
                  style={{
                    fontSize: 10,
                    color: "#3a6bff",
                    background: "#1a2a50",
                    padding: "2px 8px",
                    borderRadius: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    flexShrink: 0,
                  }}
                >
                  Open
                </span>
              )}

              {confirmId === t.id ? (
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <span style={{ color: "#ff6b6b", fontSize: 11, alignSelf: "center" }}>Delete?</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(t.id); setConfirmId(null); }}
                    style={{ padding: "3px 10px", background: "#7a1a1a", color: "#ff6b6b", border: "1px solid #9a2a2a", borderRadius: 4, fontSize: 11, cursor: "pointer" }}
                  >
                    Yes
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmId(null); }}
                    style={{ padding: "3px 10px", background: "#222", color: "#aaa", border: "1px solid #333", borderRadius: 4, fontSize: 11, cursor: "pointer" }}
                  >
                    No
                  </button>
                </div>
              ) : (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmId(t.id); }}
                  title="Delete template"
                  style={{ padding: "3px 8px", background: "transparent", color: "#555", border: "1px solid #333", borderRadius: 4, fontSize: 12, cursor: "pointer", flexShrink: 0 }}
                >
                  🗑
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── SHARED MICRO-STYLES ──────────────────────────────────────────────────────
const labelStyle: React.CSSProperties = {
  display: "block",
  color: "#666",
  fontSize: 11,
  marginBottom: 5,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "7px 10px",
  background: "#1e1e1e",
  border: "1px solid #2e2e2e",
  borderRadius: 5,
  color: "#fff",
  fontSize: 13,
  boxSizing: "border-box",
  outline: "none",
};

const primaryBtnStyle: React.CSSProperties = {
  padding: "7px 16px",
  background: "#3a6bff",
  color: "#fff",
  border: "none",
  borderRadius: 5,
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
};

const cancelBtnStyle: React.CSSProperties = {
  padding: "7px 16px",
  background: "#222",
  color: "#aaa",
  border: "1px solid #333",
  borderRadius: 5,
  cursor: "pointer",
  fontSize: 13,
};

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function CanvasEditor() {
  const {
    template,
    templates,
    bgImage,
    isBooting,
    history,
    selection,
    updateElements,
    updateElement,
    updateElementLocal,
    commit,
    addElement,
    deleteSelected,
    loadTemplate,
    createTemplate,
    deleteTemplate,
  } = useCanvasEngine();

  const shapeRefs = useRef<Record<string, Konva.Node | null>>({});
  const trRef = useRef<any>(null);
  const stageContainerRef = useRef<HTMLDivElement>(null);
  const [viewportScale, setViewportScale] = useState(1);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [qrPreviewImages, setQrPreviewImages] = useState<Record<string, HTMLImageElement>>({});

  // ── Template picker / new-template dialog state ──
  const [pickerOpen, setPickerOpen] = useState(false);
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [templateName, setTemplateName] = useState<string>("");
  const [editingName, setEditingName] = useState(false);

  // ── Sync template name when template changes ──
  useEffect(() => {
    if (template?.name) setTemplateName(template.name);
  }, [template?.name]);

  // ── Auto-open picker when workspace is empty ──
  // Suppress during boot so the picker doesn't flash while the last working
  // copy is being restored from localStorage.
  useEffect(() => {
    if (!template && !isBooting) setPickerOpen(true);
  }, [template, isBooting]);

  // ── Handlers ──
    const handleSelectTemplate = useCallback(
    (id: string) => {
      loadTemplate?.(id);
      setPickerOpen(false);
    },
    [loadTemplate]
  );

  const handleCreateTemplate = useCallback(
    async (name: string, width: number, height: number, backgroundImage?: File | null, dpi = 72) => {
      const background = backgroundImage ? await uploadBackgroundImage(backgroundImage) : "";
      await createTemplate?.(name, width, height, background, dpi);
      setNewDialogOpen(false);
      setPickerOpen(false);
    },
    [createTemplate]
  );

  const handleNameCommit = useCallback(() => {
    setEditingName(false);
    if (template && templateName.trim()) {
      updateElement?.(template.id, { name: templateName.trim() });
      commit?.({ ...template, name: templateName.trim() });
    }
  }, [template, templateName, updateElement, commit]);

  // ── Viewport / scale logic (unchanged) ──
  const calculateScale = useCallback(() => {
    if (!template || !stageContainerRef.current) return;
    const containerWidth = stageContainerRef.current.clientWidth;
    const containerHeight = stageContainerRef.current.clientHeight;
    const padding = 80;
    const availableWidth = containerWidth - padding;
    const availableHeight = containerHeight - padding;
    const scaleX = availableWidth / template.canvas.width;
    const scaleY = availableHeight / template.canvas.height;
    const scale = Math.min(scaleX, scaleY, 1);
    setViewportScale(scale);
    setStageSize({
      width: template.canvas.width * scale,
      height: template.canvas.height * scale,
    });
  }, [template]);

  useEffect(() => {
    if (!template) return;
    calculateScale();
    const ro = new ResizeObserver(calculateScale);
    if (stageContainerRef.current) ro.observe(stageContainerRef.current);
    window.addEventListener("resize", calculateScale);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", calculateScale);
    };
  }, [template, calculateScale]);

  // ── Load approved Google Fonts so Konva canvas can use them ──
  useEffect(() => {
    const id = "canvas-editor-gfonts";
    if (!document.getElementById(id)) {
      const link = document.createElement("link");
      link.id = id;
      link.rel = "stylesheet";
      link.href = buildGoogleFontsUrl(GOOGLE_LOADABLE_FONTS.map((f) => f.family));
      document.head.appendChild(link);
    }

    const localId = "canvas-editor-local-fonts";
    if (!document.getElementById(localId)) {
      const style = document.createElement("style");
      style.id = localId;
      style.textContent = BACKEND_FONTS.map(
        (f) =>
          `@font-face{font-family:'${f.family}';src:url('${API_BASE}/fonts/${f.regular}')format('truetype');font-weight:400;}` +
          `@font-face{font-family:'${f.family}';src:url('${API_BASE}/fonts/${f.bold}')format('truetype');font-weight:700;}`
      ).join("");
      document.head.appendChild(style);
    }
  }, []);

  // ── QR preview images (unchanged) ──
  useEffect(() => {
    if (!template) return;
    const qrElements = template.elements.filter((el: any) => el.type === "qr");
    qrElements.forEach((el: any) => {
      if (qrPreviewImages[el.id]) return;
      const img = new Image();
      img.crossOrigin = "Anonymous";
      const params = new URLSearchParams({
        text: QR_PREVIEW_TEXT,
        size: String(el.size),
      });
      img.src = `http://localhost:8000/render/qr-preview?${params.toString()}`;
      img.onload = () => {
        setQrPreviewImages((prev) => ({ ...prev, [el.id]: img }));
      };
    });
  }, [template, qrPreviewImages]);

  // ── Element factories (unchanged) ──
  const createTextElement = useCallback(() => {
    const id = crypto.randomUUID();
    const fontSize = 36;
    const label = "New Text";
    const textWidth = label.length * fontSize * 0.6;
    return {
      id,
      type: "text" as const,
      x: 100,
      y: 100,
      field: id,
      label,
      style: { size: fontSize, color: "#ffffff", fontFamily: DEFAULT_FONT_FAMILY, bold: false },
      boundingBox: { width: Math.round(textWidth), height: Math.round(fontSize * 1.2) } as { width: number; height: number } | null,
      overflow: "shrink-to-fit" as string,
    };
  }, []);

  const createQrElement = useCallback(() => {
    const id = crypto.randomUUID();
    return {
      id,
      type: "qr" as const,
      x: 100,
      y: 100,
      field: id,
      label: "QR Code",
      size: 120,
    };
  }, []);

  const createImageElement = useCallback(() => {
    const id = crypto.randomUUID();
    return {
      id,
      type: "image" as const,
      x: 100,
      y: 100,
      field: id,
      label: "Image Placeholder",
      boundingBox: { width: 200, height: 200 },
      maintainAspectRatio: true,
    };
  }, []);

  const handleAddText = useCallback(() => addElement(createTextElement()), [addElement, createTextElement]);
  const handleAddQr = useCallback(() => addElement(createQrElement()), [addElement, createQrElement]);
  const handleAddImage = useCallback(() => addElement(createImageElement()), [addElement, createImageElement]);

  // ── Alignment (unchanged) ──
  const handleAlign = useCallback(
    (type: AlignType) => {
      const ids = selection.selectedIds;
      if (ids.length < 2 || !template) return;
      const els = template.elements.filter((el: any) => ids.includes(el.id));
      if (els.length < 2) return;
      const bounds = els.map((el: any) => {
        const node = shapeRefs.current[el.id];
        let actualWidth: number | undefined;
        let actualHeight: number | undefined;
        if (node && el.type === "text") {
          actualWidth = node.width();
          actualHeight = node.height();
        }
        return getElementBounds(el, actualWidth, actualHeight);
      });
      const updates = alignElements(els, bounds, type);
      updateElements(updates);
    },
    [template, selection.selectedIds, updateElements]
  );

  const alignButtons: { type: AlignType; label: string; icon: string; title: string }[] = [
    { type: "left", label: "L", icon: "⫷", title: "Align Left" },
    { type: "centerX", label: "C", icon: "⇔", title: "Align Center (Horizontal)" },
    { type: "right", label: "R", icon: "⫸", title: "Align Right" },
    { type: "top", label: "T", icon: "⫵", title: "Align Top" },
    { type: "centerY", label: "M", icon: "⇕", title: "Align Middle (Vertical)" },
    { type: "bottom", label: "B", icon: "⫶", title: "Align Bottom" },
  ];

  const templateRef = useRef(template);
  templateRef.current = template;
  const commitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleDebouncedCommit = useCallback(() => {
    if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    commitTimerRef.current = setTimeout(() => {
      const current = templateRef.current;
      if (current) commit(current);
    }, 400);
  }, [commit]);

  const handleFieldChange = useCallback(
    (id: string, value: string) => {
      updateElementLocal(id, { field: value });
      scheduleDebouncedCommit();
    },
    [updateElementLocal, scheduleDebouncedCommit]
  );

  const handleLabelChange = useCallback(
    (id: string, value: string) => {
      updateElementLocal(id, { label: value });
      scheduleDebouncedCommit();
    },
    [updateElementLocal, scheduleDebouncedCommit]
  );

  // ── Transformer sync ──
  if (template) {
    const selectedNodes = selection.selectedIds
      .map((id: string) => shapeRefs.current[id])
      .filter(Boolean) as Konva.Node[];
    trRef.current?.nodes(selectedNodes);
    trRef.current?.getLayer()?.batchDraw();
  }

  // ── Render ──
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", position: "relative" }}>

      {/* ══════════════════════ TOP BAR ══════════════════════ */}
      <div
        style={{
          height: 44,
          background: "#0e0e0e",
          borderBottom: "1px solid #1e1e1e",
          display: "flex",
          alignItems: "center",
          padding: "0 12px",
          gap: 10,
          flexShrink: 0,
        }}
      >
        {/* Templates button */}
        <button
          onClick={() => setPickerOpen(true)}
          style={{
            height: 30,
            padding: "0 12px",
            background: "#1c1c1c",
            border: "1px solid #2a2a2a",
            borderRadius: 5,
            color: "#ccc",
            fontSize: 12,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ opacity: 0.5 }}>☰</span>
          Templates
        </button>

        {/* Divider */}
        <div style={{ width: 1, height: 20, background: "#2a2a2a", flexShrink: 0 }} />

        {/* Editable template name */}
        {template ? (
          editingName ? (
            <input
              autoFocus
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              onBlur={handleNameCommit}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleNameCommit();
                if (e.key === "Escape") {
                  setTemplateName(template.name ?? "");
                  setEditingName(false);
                }
              }}
              style={{
                background: "transparent",
                border: "1px solid #3a6bff",
                borderRadius: 4,
                color: "#fff",
                fontSize: 13,
                padding: "3px 8px",
                outline: "none",
                minWidth: 160,
              }}
            />
          ) : (
            <button
              onClick={() => setEditingName(true)}
              title="Click to rename"
              style={{
                background: "none",
                border: "none",
                color: "#ddd",
                fontSize: 13,
                fontWeight: 500,
                cursor: "text",
                padding: "3px 6px",
                borderRadius: 4,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {template.name || "Untitled"}
              <span style={{ color: "#444", fontSize: 10 }}>✎</span>
            </button>
          )
        ) : (
          <span style={{ color: "#444", fontSize: 13, padding: "3px 6px" }}>No template open</span>
        )}

        {/* Canvas dimensions pill */}
        {template && (
          <>
            <span
              style={{
                color: "#444",
                fontSize: 11,
                background: "#181818",
                border: "1px solid #252525",
                borderRadius: 10,
                padding: "2px 8px",
              }}
            >
              {template.canvas.width} × {template.canvas.height} px
            </span>
            <span
              style={{
                color: "#444",
                fontSize: 11,
                background: "#181818",
                border: "1px solid #252525",
                borderRadius: 10,
                padding: "2px 8px",
              }}
            >
              Print-ready workflow (300–400 DPI)
            </span>
          </>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Quick new template button */}
        <button
          onClick={() => setNewDialogOpen(true)}
          style={{
            height: 30,
            padding: "0 12px",
            background: "#1a2a50",
            border: "1px solid #2a3a6a",
            borderRadius: 5,
            color: "#7a9fff",
            fontSize: 12,
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          + New
        </button>
      </div>

      {/* ══════════════════════ BODY ══════════════════════ */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* ── LEFT TOOLBAR (unchanged) ── */}
        <div
          style={{
            width: 48,
            background: "#111",
            color: "#fff",
            borderRight: "1px solid #222",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            paddingTop: 12,
            gap: 4,
          }}
        >
          {[
            { title: "Add Text", onClick: handleAddText, label: "T" },
            { title: "Add QR Code", onClick: handleAddQr, label: "#" },
            { title: "Add Image Placeholder", onClick: handleAddImage, label: "🖼" },
          ].map((btn) => (
            <button
              key={btn.title}
              title={btn.title}
              onClick={btn.onClick}
              style={{
                width: 36,
                height: 36,
                background: "#2a2a2a",
                color: "#fff",
                border: "1px solid #333",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 14,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>

        {/* ── CANVAS ── */}
        <div
          ref={stageContainerRef}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "auto",
            background: "#1a1a1a",
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) selection.clear();
          }}
        >
          {!template ? (
            <div style={{ textAlign: "center", color: "#444", userSelect: "none" }}>
              <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>⬜</div>
              <div style={{ fontSize: 14, marginBottom: 8 }}>No template open</div>
              <div style={{ fontSize: 12, color: "#333" }}>Select or create a template to get started</div>
            </div>
          ) : (
          <Stage
            width={stageSize.width}
            height={stageSize.height}
            scaleX={viewportScale}
            scaleY={viewportScale}
            onMouseDown={(e) => {
              const target = e.target;
              const stage = target.getStage();
              if (target === stage) selection.clear();
            }}
          >
            <Layer>
              {bgImage ? (
                <KonvaImage
                  image={bgImage}
                  width={template.canvas.width}
                  height={template.canvas.height}
                  listening={false}
                />
              ) : (
                <Rect
                  width={template.canvas.width}
                  height={template.canvas.height}
                  fill="#1e1e1e"
                  listening={false}
                />
              )}

              {template.elements.map((el: any) => {
                const selected = selection.isSelected(el.id);
                const assignRef = (node: Konva.Node | null) => {
                  shapeRefs.current[el.id] = node;
                };

                if (el.type === "text") {
                  const bb = el.boundingBox ?? { width: 200, height: 44 };
                  return (
                    <Group
                      key={el.id}
                      id={el.id}
                      ref={assignRef}
                      x={el.x}
                      y={el.y}
                      width={bb.width}
                      height={bb.height}
                      draggable
                      onClick={(e) => selection.select(el.id, e.evt.shiftKey ? "toggle" : "single")}
                      onDragEnd={(e) => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                    >
                      <Rect
                        width={bb.width}
                        height={bb.height}
                        fill="rgba(255,255,255,0.01)"
                        stroke={selected ? "cyan" : "#666"}
                        strokeWidth={1}
                        dash={[4, 4]}
                      />
                      <Text
                        text={el.label}
                        fontSize={el.style.size}
                        fill={el.style.color}
                        fontFamily={el.style.fontFamily || DEFAULT_FONT_FAMILY}
                        fontStyle={el.style.bold ? "bold" : "normal"}
                        width={bb.width}
                        stroke={selected ? "cyan" : undefined}
                        listening={false}
                      />
                    </Group>
                  );
                }

                if (el.type === "qr") {
                  const qrImg = qrPreviewImages[el.id];
                  return (
                    <Group
                      key={el.id}
                      id={el.id}
                      ref={assignRef}
                      x={el.x}
                      y={el.y}
                      width={el.size}
                      height={el.size}
                      draggable
                      onClick={(e) => selection.select(el.id, e.evt.shiftKey ? "toggle" : "single")}
                      onDragEnd={(e) => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                    >
                      {qrImg ? (
                        <KonvaImage image={qrImg} width={el.size} height={el.size} />
                      ) : (
                        <Rect width={el.size} height={el.size} fill="#f0f0f0" />
                      )}
                      <Rect
                        width={el.size}
                        height={el.size}
                        stroke={selected ? "cyan" : "transparent"}
                        strokeWidth={2}
                      />
                    </Group>
                  );
                }

                if (el.type === "image") {
                  const bb = el.boundingBox ?? { width: 200, height: 200 };
                  return (
                    <Group
                      key={el.id}
                      id={el.id}
                      ref={assignRef}
                      x={el.x}
                      y={el.y}
                      width={bb.width}
                      height={bb.height}
                      draggable
                      onClick={(e) => selection.select(el.id, e.evt.shiftKey ? "toggle" : "single")}
                      onDragEnd={(e) => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                    >
                      <Rect
                        width={bb.width}
                        height={bb.height}
                        fill="rgba(100,150,255,0.1)"
                        stroke={selected ? "cyan" : "#4a7fd7"}
                        strokeWidth={2}
                        dash={[4, 4]}
                      />
                      <Text
                        text={el.label}
                        fontSize={14}
                        fill="#888"
                        x={5}
                        y={bb.height / 2 - 10}
                        width={bb.width - 10}
                        align="center"
                        listening={false}
                      />
                    </Group>
                  );
                }

                return null;
              })}

              <Transformer
                ref={trRef}
                boundBoxFunc={(oldBox, newBox) => {
                  if (newBox.width < 5 || newBox.height < 5) return oldBox;
                  return newBox;
                }}
                onTransformEnd={() => {
                  const node = trRef.current?.nodes()[0];
                  if (!node) return;
                  const id = node.id();
                  const el = template.elements.find((e: any) => e.id === id);
                  if (!el) return;
                  const currentWidth = node.width();
                  const currentScaleX = node.scaleX();
                  const currentScaleY = node.scaleY();
                  const newWidth = Math.round(currentWidth * currentScaleX);
                  if (el.type === "qr") {
                    node.scaleX(1);
                    node.scaleY(1);
                    node.width(newWidth);
                    node.height(newWidth);
                    updateElement(id, { size: newWidth });
                  } else if (el.type === "text") {
                    const bb = el.boundingBox ?? { width: 200, height: 44 };
                    const newBbWidth = Math.round(bb.width * currentScaleX);
                    const newBbHeight = Math.round(bb.height * Math.abs(currentScaleY));
                    node.scaleX(1);
                    node.scaleY(1);
                    updateElement(id, { boundingBox: { width: newBbWidth, height: newBbHeight } });
                  } else if (el.type === "image") {
                    const bb = el.boundingBox ?? { width: 200, height: 200 };
                    const newBbWidth = Math.round(bb.width * currentScaleX);
                    const newBbHeight = Math.round(bb.height * Math.abs(currentScaleY));
                    node.scaleX(1);
                    node.scaleY(1);
                    updateElement(id, { boundingBox: { width: newBbWidth, height: newBbHeight } });
                  }
                }}
              />
            </Layer>
          </Stage>
          )}
        </div>

        {/* ── RIGHT PANEL (unchanged) ── */}
        <div
          style={{
            width: 320,
            background: "#111",
            color: "#fff",
            padding: 16,
            borderLeft: "1px solid #222",
            overflowY: "auto",
          }}
        >
          <h3 style={{ margin: "0 0 12px" }}>Inspector</h3>

          <div style={{ marginBottom: 10 }}>
            {selection.selectedIds.length > 0 && (
              <span style={{ color: "#888" }}>
                {selection.selectedIds.length} selected
              </span>
            )}
          </div>

          {selection.selectedIds.length > 0 && (
            <button
              onClick={deleteSelected}
              style={{ width: "100%", padding: 8, marginBottom: 10, background: "#5a1a1a", color: "#ff6b6b", border: "1px solid #7a2a2a" }}
            >
              Delete Selected ({selection.selectedIds.length})
            </button>
          )}

          <div style={{ fontSize: 12, color: "#888" }}>Undo steps: {history.getLength()}</div>

          {selection.selectedIds.length >= 2 && (
            <div style={{ marginTop: 16, marginBottom: 16 }}>
              <div style={{ color: "#888", fontSize: 11, marginBottom: 8, textTransform: "uppercase" }}>Align</div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {alignButtons.map((btn) => (
                  <button
                    key={btn.type}
                    title={btn.title}
                    onClick={() => handleAlign(btn.type)}
                    style={{ width: 32, height: 32, background: "#2a2a2a", color: "#aaa", border: "1px solid #444", borderRadius: 4, cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center" }}
                  >
                    {btn.icon}
                  </button>
                ))}
              </div>
            </div>
          )}

          {selection.selectedIds.length === 1 && template && (() => {
            const el = template.elements.find((e: any) => e.id === selection.selectedIds[0]);
            if (!el) return null;
            return (
              <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ color: "#aaa", fontSize: 12, textTransform: "uppercase" }}>
                  {el.type === "text" ? "Text Element" : el.type === "image" ? "Image Placeholder" : "QR Code Element"}
                </div>
                <div>
                  <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Field Name</label>
                  <input value={el.field} onChange={(e) => handleFieldChange(el.id, e.target.value)} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} placeholder="e.g. event_title" />
                </div>
                <div>
                  <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Display Label</label>
                  <input value={el.label} onChange={(e) => handleLabelChange(el.id, e.target.value)} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} placeholder="e.g. Event Title" />
                </div>
                {el.type === "text" && (
                  <>
                    <div style={{ display: "flex", gap: 8 }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Box Width</label>
                        <input type="number" value={el.boundingBox?.width ?? 200} onChange={(e) => { const w = parseInt(e.target.value) || 0; const bb = el.boundingBox ?? { width: 200, height: 44 }; updateElementLocal(el.id, { boundingBox: { ...bb, width: w } }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Box Height</label>
                        <input type="number" value={el.boundingBox?.height ?? 44} onChange={(e) => { const h = parseInt(e.target.value) || 0; const bb = el.boundingBox ?? { width: 200, height: 44 }; updateElementLocal(el.id, { boundingBox: { ...bb, height: h } }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} />
                      </div>
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Font Size</label>
                      <input type="number" value={el.style?.size || 36} onChange={(e) => { const newSize = parseInt(e.target.value) || 12; updateElementLocal(el.id, { style: { ...el.style, size: newSize } }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} />
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Font Family</label>
                      <FontSelector
                        value={el.style?.fontFamily || DEFAULT_FONT_FAMILY}
                        onChange={(family) => { updateElementLocal(el.id, { style: { ...el.style, fontFamily: family } }); scheduleDebouncedCommit(); }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Font Style</label>
                      <button
                        onClick={() => { updateElementLocal(el.id, { style: { ...el.style, bold: !el.style?.bold } }); scheduleDebouncedCommit(); }}
                        style={{
                          padding: "5px 14px",
                          background: el.style?.bold ? "#3a6bff" : "#2a2a2a",
                          border: `1px solid ${el.style?.bold ? "#3a6bff" : "#444"}`,
                          borderRadius: 4,
                          color: el.style?.bold ? "#fff" : "#aaa",
                          fontSize: 13,
                          fontWeight: "bold",
                          cursor: "pointer",
                        }}
                      >
                        B
                      </button>
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Overflow Behavior</label>
                      <select value={el.overflow || "shrink-to-fit"} onChange={(e) => { updateElementLocal(el.id, { overflow: e.target.value }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }}>
                        <option value="shrink-to-fit">Shrink to Fit</option>
                        <option value="wrap">Wrap</option>
                        <option value="truncate">Truncate</option>
                      </select>
                    </div>
                    <div style={{ color: "#666", fontSize: 11 }}>
                      Pos: {el.x}, {el.y} · Size: {el.style?.size || 36}px{el.boundingBox && <> · BB: {el.boundingBox.width}×{el.boundingBox.height}</>} · {el.overflow || "shrink-to-fit"}
                    </div>
                  </>
                )}
                {el.type === "qr" && (
                  <div style={{ color: "#666", fontSize: 11 }}>Pos: {el.x}, {el.y} · Size: {el.size}px</div>
                )}
                {el.type === "image" && (
                  <>
                    <div style={{ display: "flex", gap: 8 }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Box Width</label>
                        <input type="number" value={el.boundingBox?.width ?? 200} onChange={(e) => { const w = parseInt(e.target.value) || 0; const bb = el.boundingBox ?? { width: 200, height: 200 }; updateElementLocal(el.id, { boundingBox: { ...bb, width: w } }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Box Height</label>
                        <input type="number" value={el.boundingBox?.height ?? 200} onChange={(e) => { const h = parseInt(e.target.value) || 0; const bb = el.boundingBox ?? { width: 200, height: 200 }; updateElementLocal(el.id, { boundingBox: { ...bb, height: h } }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} />
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input type="checkbox" checked={el.maintainAspectRatio ?? true} onChange={(e) => { updateElementLocal(el.id, { maintainAspectRatio: e.target.checked }); scheduleDebouncedCommit(); }} style={{ cursor: "pointer", width: 16, height: 16 }} />
                      <label style={{ color: "#888", fontSize: 11, cursor: "pointer" }}>Maintain Aspect Ratio</label>
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Source Field (optional)</label>
                      <input type="text" value={el.sourceField ?? ""} onChange={(e) => { updateElementLocal(el.id, { sourceField: e.target.value || null }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} placeholder="e.g. partner" />
                    </div>
                    <div>
                      <label style={{ display: "block", color: "#888", fontSize: 11, marginBottom: 4 }}>Asset Type (optional)</label>
                      <input type="text" value={el.assetType ?? ""} onChange={(e) => { updateElementLocal(el.id, { assetType: e.target.value || null }); scheduleDebouncedCommit(); }} style={{ width: "100%", padding: "6px 8px", background: "#222", border: "1px solid #333", borderRadius: 4, color: "#fff", fontSize: 13, boxSizing: "border-box", outline: "none" }} placeholder="e.g. logos" />
                    </div>
                    <div style={{ color: "#666", fontSize: 11 }}>
                      Pos: {el.x}, {el.y}{el.boundingBox && <> · BB: {el.boundingBox.width}×{el.boundingBox.height}</>} · AR: {el.maintainAspectRatio ? "yes" : "no"}
                    </div>
                  </>
                )}
              </div>
            );
          })()}

          {selection.selectedIds.length === 0 && (
            <div style={{ marginTop: 20, color: "#555" }}>Click an element to edit</div>
          )}
        </div>
      </div>

      {/* ══════════════ OVERLAYS ══════════════ */}
      {pickerOpen && (
        <TemplatePicker
          templates={templates}
          currentId={template?.id}
          onSelect={handleSelectTemplate}
          onNew={() => { setPickerOpen(false); setNewDialogOpen(true); }}
          onDelete={deleteTemplate}
          onClose={() => { if (template) setPickerOpen(false); }}
        />
      )}

      {newDialogOpen && (
        <NewTemplateDialog
          onConfirm={handleCreateTemplate}
          onCancel={() => setNewDialogOpen(false)}
        />
      )}
    </div>
  );
}
