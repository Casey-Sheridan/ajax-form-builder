import { createContext, useContext, useState, useCallback, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import type { FlyerData } from '../api/renderApi';

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

// Format date with ordinal suffix
function formatPrettyDate(date: Date): string {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                  'July', 'August', 'September', 'October', 'November', 'December'];
  
  const day = date.getDate();
  const ordinal = day % 100 >= 11 && day % 100 <= 13
    ? 'th'
    : ['th', 'st', 'nd', 'rd'][day % 10] || 'th';
  
  return `${days[date.getDay()]}, ${months[date.getMonth()]} ${day}${ordinal}`;
}

// Split address into two lines (used at generate time)
function splitAddress(addr: string): [string, string] {
  const parts = addr.split(',').map(p => p.trim());
  if (parts.length >= 2) {
    return [parts[0], parts.slice(1).join(', ')];
  }
  return [addr, ''];
}

export const TIME_OPTIONS = generateTimeOptions();

interface Template {
  id: string;
  name: string;
}

interface Partner {
  name: string;
  logo_url?: string;
}

interface FlyerContextValue {
  // Templates & Partners
  templates: Template[];
  setTemplates: Dispatch<SetStateAction<Template[]>>;
  partners: Partner[];
  setPartners: Dispatch<SetStateAction<Partner[]>>;
  
  // Form state
  selectedTemplate: string;
  setSelectedTemplate: Dispatch<SetStateAction<string>>;
  formData: FlyerData;
  setFormData: Dispatch<SetStateAction<FlyerData>>;
  startDate: string;
  setStartDate: Dispatch<SetStateAction<string>>;
  startTime: string;
  setStartTime: Dispatch<SetStateAction<string>>;
  endTime: string;
  setEndTime: Dispatch<SetStateAction<string>>;
  
  // Raw address (commas preserved until submission)
  rawAddress: string;
  setRawAddress: Dispatch<SetStateAction<string>>;
  
  // Partner suggestion
  suggestedPartner: Partner | null;
  setSuggestedPartner: Dispatch<SetStateAction<Partner | null>>;
  
  // Custom logo
  customLogoFile: File | null;
  setCustomLogoFile: Dispatch<SetStateAction<File | null>>;
  customLogoUrl: string;
  setCustomLogoUrl: Dispatch<SetStateAction<string>>;
  
  // Preview (store blob, derive URL in component)
  previewBlob: Blob | null;
  setPreviewBlob: Dispatch<SetStateAction<Blob | null>>;
  
  // UI state
  isLoading: boolean;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  
  // Actions
  handleLocationChange: (value: string) => void;
  handleAddressChange: (value: string) => void;
  handleFormChange: (field: string, value: string) => void;
  handleReset: () => void;
  
  // Utility: split raw address on generate
  getAddressFields: (raw: string) => { address1: string; address2: string };
}

const FlyerContext = createContext<FlyerContextValue | null>(null);

export function FlyerProvider({ children }: { children: ReactNode }) {
  // Templates & Partners
  const [templates, setTemplates] = useState<Template[]>([]);
  const [partners, setPartners] = useState<Partner[]>([{ name: 'Custom' }]);
  
  // Form state
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [formData, setFormData] = useState<FlyerData>({
    location: '',
    address1: '',
    address2: '',
    date: formatPrettyDate(new Date()),
    time: '10:00 AM - 2:00 PM',
    partner: '',
    registration_link: '',
  });
  const [startDate, setStartDate] = useState<string>(() => {
    const now = new Date();
    return now.toISOString().split('T')[0];
  });
  const [startTime, setStartTime] = useState<string>('10:00 AM');
  const [endTime, setEndTime] = useState<string>('2:00 PM');
  
  // Raw address — stored as-is so commas work in the input field
  const [rawAddress, setRawAddress] = useState<string>('');
  
  // Partner suggestion
  const [suggestedPartner, setSuggestedPartner] = useState<Partner | null>(null);
  
  // Custom logo
  const [customLogoFile, setCustomLogoFile] = useState<File | null>(null);
  const [customLogoUrl, setCustomLogoUrl] = useState<string>('');
  
  // Preview
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fuzzy match partner
  const fuzzyMatchPartner = useCallback((text: string, partnersList: Partner[]): Partner | null => {
    const lowerText = text.toLowerCase();
    
    for (const partner of partnersList) {
      if (partner.name.toLowerCase() === lowerText) return partner;
    }
    
    for (const partner of partnersList) {
      if (partner.name.toLowerCase().includes(lowerText) || 
          lowerText.includes(partner.name.toLowerCase().substring(0, 3))) {
        return partner;
      }
    }
    
    return null;
  }, []);

  // Get address fields from raw address (used at generate time)
  const getAddressFields = useCallback((raw: string): { address1: string; address2: string } => {
    const [addr1, addr2] = splitAddress(raw);
    return { address1: addr1, address2: addr2 };
  }, []);

  // Handle location change and partner suggestion
  const handleLocationChange = useCallback((value: string) => {
    setFormData(prev => ({ ...prev, location: value }));
    
    const match = fuzzyMatchPartner(value, partners);
    setSuggestedPartner(match);
    
    if (match && match.name !== 'Custom') {
      setFormData(prev => ({ ...prev, partner: match.name }));
    }
  }, [partners, fuzzyMatchPartner]);

  // Handle address change — store raw text, split only at generation time
  const handleAddressChange = useCallback((value: string) => {
    setRawAddress(value);
  }, []);

  // Handle form changes
  const handleFormChange = useCallback((field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  }, []);

  // Reset form
  const handleReset = useCallback(() => {
    setFormData({
      location: '',
      address1: '',
      address2: '',
      date: formatPrettyDate(new Date()),
      time: '10:00 AM - 2:00 PM',
      partner: '',
      registration_link: '',
    });
    setStartDate(new Date().toISOString().split('T')[0]);
    setStartTime('10:00 AM');
    setEndTime('2:00 PM');
    setRawAddress('');
    setSuggestedPartner(null);
    setCustomLogoFile(null);
    setCustomLogoUrl('');
    setPreviewBlob(null);
    setError(null);
  }, []);

  return (
    <FlyerContext.Provider
      value={{
        templates,
        setTemplates,
        partners,
        setPartners,
        selectedTemplate,
        setSelectedTemplate,
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
        suggestedPartner,
        setSuggestedPartner,
        customLogoFile,
        setCustomLogoFile,
        customLogoUrl,
        setCustomLogoUrl,
        previewBlob,
        setPreviewBlob,
        isLoading,
        setIsLoading,
        error,
        setError,
        handleLocationChange,
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
  if (!ctx) {
    throw new Error('useFlyerContext must be used within a FlyerProvider');
  }
  return ctx;
}