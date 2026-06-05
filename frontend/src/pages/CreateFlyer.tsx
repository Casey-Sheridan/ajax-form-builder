import { useState, useEffect, useCallback } from 'react';
import { renderFlyer } from '../api/renderApi';
import { templateApi, uploadApi, type FieldDescriptor, type CatalogItem } from '../api/templateApi';
import { useFlyerContext, TIME_OPTIONS, fuzzyMatchCatalogItem } from '../context/FlyerContext';

// ---------------------------
// DATE HELPERS
// ---------------------------

function formatPrettyDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  const d = date.getDate();
  const ordinal = (d % 100 >= 11 && d % 100 <= 13)
    ? 'th'
    : (['th', 'st', 'nd', 'rd'][d % 10] || 'th');
  return `${days[date.getDay()]}, ${months[date.getMonth()]} ${d}${ordinal}`;
}

// ---------------------------
// FIELD RENDERERS
// ---------------------------

interface FieldProps {
  field: FieldDescriptor;
  value: string;
  onChange: (key: string, value: string) => void;
  // extras passed down only for fields that need them
  rawAddress?: string;
  onAddressChange?: (v: string) => void;
  startDate?: string;
  onStartDateChange?: (v: string) => void;
  startTime?: string;
  onStartTimeChange?: (v: string) => void;
  endTime?: string;
  onEndTimeChange?: (v: string) => void;
  catalogItems?: CatalogItem[];
  // image URL for the currently-selected catalog item
  imageValue?: string;
  onImageChange?: (key: string, url: string) => void;
}

// SelectField is its own component so it can use hooks for upload state.
function SelectField({
  field,
  value,
  onChange,
  catalogItems,
  imageValue,
  onImageChange,
}: {
  field: FieldDescriptor;
  value: string;
  onChange: (key: string, value: string) => void;
  catalogItems: CatalogItem[];
  imageValue: string;
  onImageChange: (key: string, url: string) => void;
}) {
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [localPreview, setLocalPreview] = useState<string | null>(null);
  const imageKey = field.key + '_image';

  // Reset custom mode when the form is cleared
  useEffect(() => {
    if (!value) {
      setIsCustomMode(false);
      setUploadError(null);
      setLocalPreview(null);
    }
  }, [value]);

  // Clean up object URLs on unmount
  useEffect(() => () => { if (localPreview) URL.revokeObjectURL(localPreview); }, [localPreview]);

  const handleSelect = (selected: string) => {
    if (selected === '__custom__') {
      setIsCustomMode(true);
      onChange(field.key, '');
      onImageChange(imageKey, '');
    } else {
      setIsCustomMode(false);
      onChange(field.key, selected);
      const item = catalogItems.find(i => i.value === selected);
      onImageChange(imageKey, item?.image_url ?? '');
    }
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Immediate local preview while upload is in flight
    if (localPreview) URL.revokeObjectURL(localPreview);
    setLocalPreview(URL.createObjectURL(file));
    setUploading(true);
    setUploadError(null);

    try {
      const { url } = await uploadApi.uploadTemp(file);
      onImageChange(imageKey, url);
    } catch {
      setUploadError('Upload failed — try again');
      setLocalPreview(null);
    } finally {
      setUploading(false);
    }
  };

  const previewSrc = imageValue || localPreview;

  return (
    <>
      <select
        style={styles.select}
        value={isCustomMode ? '__custom__' : value}
        onChange={e => handleSelect(e.target.value)}
      >
        <option value="">Select {field.label.toLowerCase()}…</option>
        {catalogItems.map(item => (
          <option key={item.id} value={item.value}>{item.label}</option>
        ))}
        {field.allow_custom && <option value="__custom__">Custom…</option>}
      </select>

      {isCustomMode && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            type="text"
            style={styles.input}
            value={value}
            onChange={e => onChange(field.key, e.target.value)}
            placeholder={`Enter ${field.label.toLowerCase()} name…`}
          />
          <label style={styles.fileUploadLabel}>
            <input
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleFile}
            />
            <span style={styles.fileUploadBtn}>
              {uploading ? 'Uploading…' : previewSrc ? 'Replace image' : 'Choose image…'}
            </span>
          </label>
          {uploadError && <span style={styles.uploadError}>{uploadError}</span>}
          {previewSrc && (
            <img src={previewSrc} alt="Preview" style={styles.imagePreview} />
          )}
        </div>
      )}
    </>
  );
}

function FieldInput({
  field,
  value,
  onChange,
  rawAddress,
  onAddressChange,
  startDate,
  onStartDateChange,
  startTime,
  onStartTimeChange,
  endTime,
  onEndTimeChange,
  catalogItems,
  imageValue,
  onImageChange,
}: FieldProps) {
  const placeholder = field.placeholder ?? '';

  switch (field.type) {
    case 'address':
      return (
        <input
          type="text"
          style={styles.input}
          value={rawAddress ?? ''}
          onChange={e => onAddressChange?.(e.target.value)}
          placeholder={placeholder || 'Street, City, State ZIP'}
        />
      );

    case 'date':
      return (
        <>
          <input
            type="date"
            style={styles.input}
            value={startDate ?? ''}
            onChange={e => onStartDateChange?.(e.target.value)}
          />
          {startDate && (
            <span style={styles.previewText}>{formatPrettyDate(startDate)}</span>
          )}
        </>
      );

    case 'time':
      return (
        <select
          style={styles.select}
          value={value}
          onChange={e => onChange(field.key, e.target.value)}
        >
          {TIME_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      );

    case 'timeRange':
      return (
        <div style={styles.timeRow}>
          <div style={styles.timeCol}>
            <span style={styles.timeLabel}>Start</span>
            <select
              style={styles.select}
              value={startTime ?? ''}
              onChange={e => onStartTimeChange?.(e.target.value)}
            >
              {TIME_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div style={styles.timeCol}>
            <span style={styles.timeLabel}>End</span>
            <select
              style={styles.select}
              value={endTime ?? ''}
              onChange={e => onEndTimeChange?.(e.target.value)}
            >
              {TIME_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
      );

    case 'select':
      return (
        <SelectField
          field={field}
          value={value}
          onChange={onChange}
          catalogItems={catalogItems ?? []}
          imageValue={imageValue ?? ''}
          onImageChange={onImageChange ?? (() => {})}
        />
      );

    case 'url':
      return (
        <input
          type="url"
          style={styles.input}
          value={value}
          onChange={e => onChange(field.key, e.target.value)}
          placeholder={placeholder || 'https://…'}
        />
      );

    case 'image':
      // Image fields are derived from catalog selection — no form element needed
      return null;

    default:
      return (
        <input
          type="text"
          style={styles.input}
          value={value}
          onChange={e => onChange(field.key, e.target.value)}
          placeholder={placeholder}
        />
      );
  }
}

// ---------------------------
// MAIN COMPONENT
// ---------------------------

export default function CreateFlyer() {
  const {
    templates,
    setTemplates,
    selectedTemplate,
    setSelectedTemplate,
    templateDetail,
    setTemplateDetail,
    formData,
    setFormData,
    startDate,
    setStartDate,
    startTime,
    setStartTime,
    endTime,
    setEndTime,
    rawAddress,
    orgId,
    setOrgId,
    catalogs,
    loadCatalog,
    previewBlob,
    setPreviewBlob,
    isLoading,
    setIsLoading,
    error,
    setError,
    handleAddressChange,
    handleFormChange,
    handleReset,
    getAddressFields,
  } = useFlyerContext();

  const [isHoveringPreview, setIsHoveringPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Create/destroy object URL from the persisted blob
  useEffect(() => {
    if (previewBlob) {
      const url = URL.createObjectURL(previewBlob);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreviewUrl(null);
  }, [previewBlob]);

  // Load templates on mount; bootstrap org from first org in DB
  useEffect(() => {
    if (templates.length > 0) return;

    const load = async () => {
      try {
        const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

        // Fetch templates
        const tRes = await fetch(`${API}/templates`);
        if (tRes.ok) {
          const tData = await tRes.json();
          setTemplates(tData);
          if (tData.length > 0 && !selectedTemplate) {
            setSelectedTemplate(tData[0].id);
          }
        }

        // Bootstrap org id from the default org
        if (!orgId) {
          const oRes = await fetch(`${API}/orgs`);
          if (oRes.ok) {
            const orgs = await oRes.json();
            if (orgs.length > 0) setOrgId(orgs[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to load initial data:', err);
      }
    };

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When the selected template changes, load its full definition + its catalogs
  useEffect(() => {
    if (!selectedTemplate) return;
    let cancelled = false;

    templateApi.get(selectedTemplate).then(tmpl => {
      if (cancelled) return;
      setTemplateDetail(tmpl);

      // Pre-fetch catalogs for select fields and fuzzy-catalog derived fields
      tmpl.fields.forEach(f => {
        if (f.type === 'select' && f.catalog) loadCatalog(f.catalog);
        if (f.derivation?.strategy === 'fuzzy-catalog' && f.derivation.catalog) {
          loadCatalog(f.derivation.catalog);
        }
      });
    }).catch(console.error);

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplate]);

  // Derive formData date value from the date picker state
  // The field key for date/timeRange comes from the template; we write
  // to whichever field has that type, defaulting to "date" / "time".
  useEffect(() => {
    if (!startDate) return;
    const dateField = templateDetail?.fields.find(f => f.type === 'date');
    const key = dateField?.key ?? 'date';
    setFormData(prev => ({ ...prev, [key]: formatPrettyDate(startDate) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, templateDetail]);

  useEffect(() => {
    const timeRangeField = templateDetail?.fields.find(f => f.type === 'timeRange');
    const key = timeRangeField?.key ?? 'time';
    setFormData(prev => ({ ...prev, [key]: `${startTime} - ${endTime}` }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startTime, endTime, templateDetail]);

  // Evaluate fuzzy-catalog derivations whenever formData changes
  useEffect(() => {
    if (!templateDetail) return;
    const derived = templateDetail.fields.filter(
      f => f.derivation?.strategy === 'fuzzy-catalog' && f.derivation.catalog && f.derivation.sourceField,
    );
    if (derived.length === 0) return;

    const patches: Record<string, string> = {};
    derived.forEach(f => {
      const { sourceField, catalog } = f.derivation!;
      const sourceValue = formData[sourceField] ?? '';
      const items = catalogs[catalog!] ?? [];
      const match = fuzzyMatchCatalogItem(sourceValue, items);
      if (match) {
        patches[f.key] = match.value;
        if (match.image_url) patches[f.key + '_image'] = match.image_url;
      }
    });

    if (Object.keys(patches).length > 0) {
      setFormData(prev => ({ ...prev, ...patches }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, templateDetail, catalogs]);

  // Generate flyer
  const handleGenerate = useCallback(async () => {
    if (!selectedTemplate) {
      setError('Please select a template');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const { address1, address2 } = getAddressFields(rawAddress);
      const renderData = {
        ...formData,
        address1,
        address2,
        address: [address1, address2].filter(Boolean).join(', '),
      };

      const blob = await renderFlyer({ template_id: selectedTemplate, data: renderData });
      setPreviewBlob(blob);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate flyer');
      console.error('Render error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedTemplate, formData, rawAddress, getAddressFields, setPreviewBlob, setError, setIsLoading]);

  // Download flyer
  const handleDownload = useCallback(() => {
    if (!previewUrl) return;
    const a = document.createElement('a');
    a.href = previewUrl;
    a.download = 'Final_Flyer.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [previewUrl]);

  // Render one form field
  const renderField = (field: FieldDescriptor) => {
    if (field.type === 'image') return null;

    const imageKey = field.key + '_image';
    const catalogItems = field.catalog ? (catalogs[field.catalog] ?? []) : undefined;

    return (
      <div key={field.key} style={styles.formGroup}>
        <label style={styles.label}>{field.label}</label>
        <FieldInput
          field={field}
          value={formData[field.key] ?? ''}
          onChange={handleFormChange}
          rawAddress={field.type === 'address' ? rawAddress : undefined}
          onAddressChange={field.type === 'address' ? handleAddressChange : undefined}
          startDate={field.type === 'date' ? startDate : undefined}
          onStartDateChange={field.type === 'date' ? setStartDate : undefined}
          startTime={field.type === 'timeRange' ? startTime : undefined}
          onStartTimeChange={field.type === 'timeRange' ? setStartTime : undefined}
          endTime={field.type === 'timeRange' ? endTime : undefined}
          onEndTimeChange={field.type === 'timeRange' ? setEndTime : undefined}
          catalogItems={catalogItems}
          imageValue={formData[imageKey]}
          onImageChange={handleFormChange}
        />
      </div>
    );
  };

  const visibleFields = (templateDetail?.fields ?? []).filter(f => f.type !== 'image');

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Left Panel — Form */}
        <div style={styles.formPanel}>
          <h2 style={styles.panelTitle}>Create Flyer</h2>

          {/* Template selector */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Template</label>
            <select
              style={styles.select}
              value={selectedTemplate}
              onChange={e => setSelectedTemplate(e.target.value)}
            >
              {templates.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Dynamic fields from the template */}
          {visibleFields.map(renderField)}

          {error && <div style={styles.error}>{error}</div>}

          <div style={styles.buttonRow}>
            <button
              style={{ ...styles.button, ...styles.primaryButton, opacity: isLoading ? 0.7 : 1 }}
              onClick={handleGenerate}
              disabled={isLoading}
            >
              {isLoading ? 'Generating…' : 'Generate'}
            </button>
            <button
              style={{ ...styles.button, ...styles.secondaryButton }}
              onClick={handleReset}
            >
              Reset
            </button>
          </div>
        </div>

        {/* Right Panel — Preview */}
        <div style={styles.previewPanel}>
          <h2 style={styles.panelTitle}>Preview</h2>
          <div
            style={styles.previewContainer}
            onMouseEnter={() => setIsHoveringPreview(true)}
            onMouseLeave={() => setIsHoveringPreview(false)}
          >
            {isLoading ? (
              <div style={styles.loadingSpinner}>
                <div style={styles.spinner} />
                <span>Generating flyer…</span>
              </div>
            ) : previewUrl ? (
              <>
                <img src={previewUrl} alt="Generated Flyer" style={styles.previewImage} />
                {isHoveringPreview && (
                  <button style={styles.downloadButton} onClick={handleDownload}>
                    ⬇ Download
                  </button>
                )}
              </>
            ) : (
              <div style={styles.placeholder}>
                <p>Fill out the form and click "Generate" to see a preview</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------
// STYLES
// ---------------------------
const styles: { [key: string]: React.CSSProperties } = {
  container: { minHeight: '100vh', background: '#1a1a1a', padding: '20px' },
  content: { maxWidth: '1400px', margin: '0 auto', display: 'flex', gap: '30px' },
  formPanel: {
    flex: 1, maxWidth: '500px', background: '#252525',
    borderRadius: '12px', padding: '24px', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  },
  previewPanel: {
    flex: 1, background: '#252525',
    borderRadius: '12px', padding: '24px', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  },
  panelTitle: {
    color: '#fff', fontSize: '24px', fontWeight: 600,
    marginBottom: '24px', paddingBottom: '12px', borderBottom: '1px solid #333',
  },
  formGroup: { marginBottom: '20px' },
  label: { display: 'block', color: '#aaa', fontSize: '14px', fontWeight: 500, marginBottom: '6px' },
  input: {
    width: '100%', padding: '10px 14px', background: '#333',
    border: '1px solid #444', borderRadius: '8px', color: '#fff',
    fontSize: '14px', boxSizing: 'border-box', outline: 'none',
  },
  select: {
    width: '100%', padding: '10px 14px', background: '#333',
    border: '1px solid #444', borderRadius: '8px', color: '#fff',
    fontSize: '14px', boxSizing: 'border-box', outline: 'none', cursor: 'pointer',
  },
  previewText: { display: 'block', color: '#888', fontSize: '12px', marginTop: '4px' },
  timeRow: { display: 'flex', gap: '12px' },
  timeCol: { flex: 1 },
  timeLabel: { display: 'block', color: '#888', fontSize: '12px', marginBottom: '4px' },
  error: {
    background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444',
    borderRadius: '8px', padding: '12px', color: '#ef4444',
    fontSize: '14px', marginBottom: '16px',
  },
  buttonRow: { display: 'flex', gap: '12px', marginTop: '24px' },
  button: {
    flex: 1, padding: '12px 20px', borderRadius: '8px',
    fontSize: '14px', fontWeight: 600, cursor: 'pointer', border: 'none',
  },
  primaryButton: { background: '#3b82f6', color: '#fff' },
  secondaryButton: { background: '#444', color: '#fff' },
  previewContainer: {
    position: 'relative', display: 'flex', alignItems: 'center',
    justifyContent: 'center', minHeight: '400px', background: '#1a1a1a',
    borderRadius: '8px', overflow: 'hidden',
  },
  placeholder: { color: '#666', textAlign: 'center', padding: '40px' },
  previewImage: { maxWidth: '100%', maxHeight: '500px', objectFit: 'contain' },
  downloadButton: {
    position: 'absolute', top: '10px', right: '10px',
    padding: '8px 16px', background: 'rgba(0,0,0,0.7)',
    color: '#fff', border: 'none', borderRadius: '6px',
    cursor: 'pointer', fontSize: '14px',
  },
  loadingSpinner: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', color: '#888',
  },
  spinner: {
    width: '40px', height: '40px', border: '3px solid #333',
    borderTop: '3px solid #3b82f6', borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
  fileUploadLabel: { cursor: 'pointer', display: 'block' },
  fileUploadBtn: {
    display: 'block', padding: '10px 14px', background: '#333',
    border: '1px solid #444', borderRadius: '8px', color: '#aaa',
    fontSize: '14px', textAlign: 'center' as const, cursor: 'pointer',
  },
  uploadError: { color: '#ef4444', fontSize: '12px' },
  imagePreview: {
    maxWidth: '100%', maxHeight: '80px', objectFit: 'contain' as const,
    borderRadius: '6px', border: '1px solid #444',
  },
};

if (!document.getElementById('flyer-spinner-styles')) {
  const s = document.createElement('style');
  s.id = 'flyer-spinner-styles';
  s.textContent = `@keyframes spin { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }`;
  document.head.appendChild(s);
}
