import type { FieldDescriptor, FieldType, DateFormat } from "../../api/templateApi";

const KNOWN_FIELD_TYPES: Record<string, { type: FieldType; date_format?: DateFormat }> = {
  date: { type: "date", date_format: "long_no_year" },
  time: { type: "time" },
  registration_link: { type: "url" },
  partner: { type: "partner" },
  address: { type: "address" },
  address1: { type: "address" },
  address2: { type: "address" },
};

// Elements whose field type should be forced to "image" in derived descriptors.
const IMAGE_ELEMENT_TYPE = "image";

// "address1" → "address", "venue_address2" → "venue_address", otherwise null.
function addressRootKey(key: string): string | null {
  if (key === "address1" || key === "address2") return "address";
  const m = key.match(/^(.+_address)[12]$/);
  return m ? m[1] : null;
}

// Produces a human-readable label from a snake_case key.
function labelFromKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// Collapses address1/address2 (and foo_address1/foo_address2) siblings into a
// single root descriptor so the form shows one input per logical address.
function collapseAddressFields(fields: FieldDescriptor[]): FieldDescriptor[] {
  const result: FieldDescriptor[] = [];
  const emitted = new Set<string>();
  for (const f of fields) {
    const root = addressRootKey(f.key);
    if (root) {
      if (!emitted.has(root)) {
        emitted.add(root);
        result.push({ key: root, type: "address", label: labelFromKey(root), required: f.required });
      }
      emitted.add(f.key);
    } else if (!emitted.has(f.key)) {
      emitted.add(f.key);
      result.push(f);
    }
  }
  return result;
}

function deriveFields(elements: any[]): FieldDescriptor[] {
  const seen = new Set<string>();
  const fields: FieldDescriptor[] = [];
  for (const el of elements) {
    if (el?.field && !seen.has(el.field)) {
      seen.add(el.field);
      const isImage = el.type === IMAGE_ELEMENT_TYPE;
      const defaults = KNOWN_FIELD_TYPES[el.field] ?? { type: (isImage ? "image" : "text") as FieldType };
      const fd: FieldDescriptor = {
        key: el.field,
        label: el.label ?? el.field,
        required: true,
        ...defaults,
      };
      // Carry element-level sourceField/assetType into a field-level derivation.
      if (isImage && el.sourceField) {
        fd.derivation = {
          strategy: "asset-lookup",
          sourceField: el.sourceField,
          ...(el.assetType ? { assetType: el.assetType } : {}),
        };
      }
      fields.push(fd);
    }
  }
  return fields;
}

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

  // Use saved fields, or lazily derive from elements for legacy templates.
  // Either way, collapse address1/address2 siblings into one root descriptor.
  const rawFields: FieldDescriptor[] = collapseAddressFields(
    Array.isArray(data.fields) && data.fields.length > 0
      ? data.fields
      : deriveFields(elements)
  );

  // For templates with saved fields that predate derivation support: if an
  // image element has sourceField/assetType on the element itself but the
  // corresponding field descriptor has no derivation yet, migrate it now.
  const fieldMap = new Map(rawFields.map((f) => [f.key, f]));
  for (const el of elements) {
    if (el?.type === IMAGE_ELEMENT_TYPE && el.sourceField) {
      const fd = fieldMap.get(el.field);
      if (fd && !fd.derivation) {
        fd.type = "image";
        fd.derivation = {
          strategy: "asset-lookup",
          sourceField: el.sourceField,
          ...(el.assetType ? { assetType: el.assetType } : {}),
        };
      }
    }
  }
  const fields = [...fieldMap.values()];

  return {
    id: data.id,
    name: data.name ?? "",
    canvas: data.canvas ?? { width: 1080, height: 1350 },
    background: bg,
    elements,
    fields,
  };
}
