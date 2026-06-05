import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
  type Dispatch,
  type SetStateAction,
} from 'react';
import type { FlyerData } from '../api/renderApi';
import type { CatalogItem, TemplateDTO } from '../api/templateApi';
import { catalogApi } from '../api/templateApi';
import { parseUSAddress } from '../utils/addressParser';

// Time options generator (6 AM to 10:30 PM, 30-min intervals)
function generateTimeOptions(): string[] {
  const times: string[] = [];
  for (let hour = 6; hour <= 22; hour++) {
    for (let minute = 0; minute < 60; minute += 30) {
      if (hour === 22 && minute === 30) continue;
      const suffix = hour < 12 ? 'AM' : 'PM';
      const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
      times.push(`${displayHour}:${minute.toString().padStart(2, '0')} ${suffix}`);
    }
  }
  return times;
}

export const TIME_OPTIONS = generateTimeOptions();

interface Template {
  id: string;
  name: string;
}

export function fuzzyMatchCatalogItem(
  text: string,
  items: CatalogItem[],
): CatalogItem | null {
  const lower = text.toLowerCase().trim();
  if (!lower) return null;

  for (const item of items) {
    if (item.label.toLowerCase() === lower) return item;
  }

  for (const item of items) {
    const itemLower = item.label.toLowerCase();
    if (itemLower.includes(lower) || lower.includes(itemLower.substring(0, 3))) {
      return item;
    }
  }

  return null;
}

interface FlyerContextValue {
  // Templates
  templates: Template[];
  setTemplates: Dispatch<SetStateAction<Template[]>>;
  selectedTemplate: string;
  setSelectedTemplate: Dispatch<SetStateAction<string>>;
  templateDetail: TemplateDTO | null;
  setTemplateDetail: Dispatch<SetStateAction<TemplateDTO | null>>;

  // Form state (generic — driven by template.fields)
  formData: FlyerData;
  setFormData: Dispatch<SetStateAction<FlyerData>>;

  // Special state for complex field types
  startDate: string;
  setStartDate: Dispatch<SetStateAction<string>>;
  startTime: string;
  setStartTime: Dispatch<SetStateAction<string>>;
  endTime: string;
  setEndTime: Dispatch<SetStateAction<string>>;
  rawAddress: string;
  setRawAddress: Dispatch<SetStateAction<string>>;

  // Org (no auth yet — defaults to first org in DB)
  orgId: string | null;
  setOrgId: Dispatch<SetStateAction<string | null>>;

  // Catalogs — keyed by catalog name, populated on demand
  catalogs: Record<string, CatalogItem[]>;
  loadCatalog: (name: string) => Promise<void>;

  // Preview
  previewBlob: Blob | null;
  setPreviewBlob: Dispatch<SetStateAction<Blob | null>>;

  // UI state
  isLoading: boolean;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;

  // Actions
  handleAddressChange: (value: string) => void;
  handleFormChange: (field: string, value: string) => void;
  handleReset: () => void;
  getAddressFields: (raw: string) => { address1: string; address2: string };
}

const FlyerContext = createContext<FlyerContextValue | null>(null);

export function FlyerProvider({ children }: { children: ReactNode }) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [templateDetail, setTemplateDetail] = useState<TemplateDTO | null>(null);

  const [formData, setFormData] = useState<FlyerData>({});

  const [startDate, setStartDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState<string>('10:00 AM');
  const [endTime, setEndTime] = useState<string>('2:00 PM');
  const [rawAddress, setRawAddress] = useState<string>('');

  const [orgId, setOrgId] = useState<string | null>(null);

  // Catalog cache — avoids re-fetching the same catalog within a session
  const [catalogs, setCatalogs] = useState<Record<string, CatalogItem[]>>({});
  const fetchingRef = useRef<Set<string>>(new Set());

  const loadCatalog = useCallback(async (name: string) => {
    if (catalogs[name] !== undefined) return;
    if (fetchingRef.current.has(name)) return;
    fetchingRef.current.add(name);
    try {
      const items = await catalogApi.list(name, orgId ?? undefined);
      setCatalogs(prev => ({ ...prev, [name]: items }));
    } finally {
      fetchingRef.current.delete(name);
    }
  }, [catalogs, orgId]);

  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAddressFields = useCallback((raw: string): { address1: string; address2: string } => {
    const [addr1, addr2] = parseUSAddress(raw);
    return { address1: addr1, address2: addr2 };
  }, []);

  const handleAddressChange = useCallback((value: string) => {
    setRawAddress(value);
  }, []);

  const handleFormChange = useCallback((field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  }, []);

  const handleReset = useCallback(() => {
    setFormData({});
    setStartDate(new Date().toISOString().split('T')[0]);
    setStartTime('10:00 AM');
    setEndTime('2:00 PM');
    setRawAddress('');
    setPreviewBlob(null);
    setError(null);
  }, []);

  return (
    <FlyerContext.Provider
      value={{
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
        setRawAddress,
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
      }}
    >
      {children}
    </FlyerContext.Provider>
  );
}

export function useFlyerContext(): FlyerContextValue {
  const ctx = useContext(FlyerContext);
  if (!ctx) throw new Error('useFlyerContext must be used within a FlyerProvider');
  return ctx;
}
