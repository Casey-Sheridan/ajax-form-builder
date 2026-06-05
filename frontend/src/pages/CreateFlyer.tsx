import { useState, useEffect, useCallback } from 'react';
import { renderFlyer, type FlyerData } from '../api/renderApi';
import { useFlyerContext, TIME_OPTIONS } from '../context/FlyerContext';

export default function CreateFlyer() {
  const {
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
    suggestedPartner,
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
    rawAddress,
  } = useFlyerContext();

  const [isHoveringPreview, setIsHoveringPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Create/destroy object URL from the persisted blob
  useEffect(() => {
    if (previewBlob) {
      const url = URL.createObjectURL(previewBlob);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [previewBlob]);

  // Load templates and partners on mount (only if not already loaded)
  useEffect(() => {
    if (templates.length > 0) return;

    const loadData = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        
        // Load templates
        const templatesRes = await fetch(`${API_BASE_URL}/templates`);
        if (templatesRes.ok) {
          const templatesData = await templatesRes.json();
          setTemplates(templatesData);
          if (templatesData.length > 0 && !selectedTemplate) {
            setSelectedTemplate(templatesData[0].id);
          }
        }
        
        // Load partners
        const partnersRes = await fetch(`${API_BASE_URL}/partners`);
        if (partnersRes.ok) {
          const partnersData = await partnersRes.json();
          setPartners(partnersData);
        }
      } catch (err) {
        console.error('Failed to load data:', err);
      }
    };
    
    loadData();
    // Only run on mount; after that the context holds the data
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update time range when start/end change
  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      time: `${startTime} - ${endTime}`
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startTime, endTime]);

  // Update date when date picker changes
  useEffect(() => {
    if (startDate) {
      const [year, month, day] = startDate.split('-').map(Number);
      const date = new Date(year, month - 1, day);
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                      'July', 'August', 'September', 'October', 'November', 'December'];
      const dayOfMonth = date.getDate();
      const ordinal = dayOfMonth % 100 >= 11 && dayOfMonth % 100 <= 13
        ? 'th'
        : ['th', 'st', 'nd', 'rd'][dayOfMonth % 10] || 'th';
      const prettyDate = `${days[date.getDay()]}, ${months[date.getMonth()]} ${date.getDate()}${ordinal}`;
      setFormData(prev => ({
        ...prev,
        date: prettyDate
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate]);

  // Generate flyer
  const handleGenerate = useCallback(async () => {
    if (!selectedTemplate) {
      setError('Please select a template');
      return;
    }
    
    if (formData.partner === 'Custom' && !customLogoFile && !customLogoUrl) {
      setError('Custom partner requires a logo (file or URL)');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Split raw address into address1/address2 at generation time
      const { address1, address2 } = getAddressFields(rawAddress);
      // Combine address fields to match template field names (e.g. "address")
      const combinedAddress = [address1, address2].filter(Boolean).join(', ');
      const renderData: FlyerData & Record<string, string> = { ...formData, address1, address2, address: combinedAddress };
      if (formData.partner === 'Custom' && customLogoUrl) {
        renderData.logo_url = customLogoUrl;
      }
      
      const blob = await renderFlyer({
        template_id: selectedTemplate,
        data: renderData,
      });

      setPreviewBlob(blob);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate flyer');
      console.error('Render error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [
    selectedTemplate,
    formData,
    rawAddress,
    getAddressFields,
    customLogoFile,
    customLogoUrl,
    setPreviewBlob,
    setError,
    setIsLoading,
  ]);

  // Download flyer
  const handleDownload = useCallback(() => {
    if (!previewUrl) return;
    
    const link = document.createElement('a');
    link.href = previewUrl;
    link.download = 'Final_Flyer.png';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [previewUrl]);

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Left Panel - Form */}
        <div style={styles.formPanel}>
          <h2 style={styles.panelTitle}>Create Flyer</h2>
          
          {/* Template Selector */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Template</label>
            <select
              style={styles.select}
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
            >
              {templates.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Location */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Location Name</label>
            <input
              type="text"
              style={styles.input}
              value={formData.location}
              onChange={(e) => handleLocationChange(e.target.value)}
              placeholder="Enter location name"
            />
            {suggestedPartner && suggestedPartner.name !== 'Custom' && (
              <span style={styles.suggestion}>
                Suggested partner: {suggestedPartner.name}
              </span>
            )}
          </div>

          {/* Address — uses rawAddress so commas can be typed freely */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Address</label>
            <input
              type="text"
              style={styles.input}
              value={rawAddress}
              onChange={(e) => handleAddressChange(e.target.value)}
              placeholder="Street, City, State ZIP"
            />
          </div>

          {/* Date */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Date</label>
            <input
              type="date"
              style={styles.input}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <span style={styles.previewText}>
              {formData.date}
            </span>
          </div>

          {/* Time Range */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Time Range</label>
            <div style={styles.timeRow}>
              <div style={styles.timeCol}>
                <span style={styles.timeLabel}>Start</span>
                <select
                  style={styles.select}
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                >
                  {TIME_OPTIONS.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div style={styles.timeCol}>
                <span style={styles.timeLabel}>End</span>
                <select
                  style={styles.select}
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                >
                  {TIME_OPTIONS.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Registration Link */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Registration Link</label>
            <input
              type="url"
              style={styles.input}
              value={formData.registration_link}
              onChange={(e) => handleFormChange('registration_link', e.target.value)}
              placeholder="https://..."
            />
          </div>

          {/* Partner */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Partner</label>
            <select
              style={styles.select}
              value={formData.partner}
              onChange={(e) => handleFormChange('partner', e.target.value)}
            >
              <option value="">Select a partner</option>
              {partners.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Custom Partner Logo Options */}
          {formData.partner === 'Custom' && (
            <div style={styles.formGroup}>
              <label style={styles.label}>Logo</label>
              <div style={styles.fileInputWrapper}>
                <input
                  type="file"
                  accept="image/*"
                  style={styles.fileInput}
                  onChange={(e) => setCustomLogoFile(e.target.files?.[0] || null)}
                />
                <span style={styles.fileInputText}>
                  {customLogoFile ? customLogoFile.name : 'Choose file...'}
                </span>
              </div>
              <div style={styles.dividerText}>or</div>
              <input
                type="url"
                style={styles.input}
                value={customLogoUrl}
                onChange={(e) => setCustomLogoUrl(e.target.value)}
                placeholder="Logo URL"
              />
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div style={styles.error}>
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div style={styles.buttonRow}>
            <button
              style={{
                ...styles.button,
                ...styles.primaryButton,
                opacity: isLoading ? 0.7 : 1,
              }}
              onClick={handleGenerate}
              disabled={isLoading}
            >
              {isLoading ? 'Generating...' : 'Generate'}
            </button>
            <button
              style={{ ...styles.button, ...styles.secondaryButton }}
              onClick={handleReset}
            >
              Reset
            </button>
          </div>
        </div>

        {/* Right Panel - Preview */}
        <div style={styles.previewPanel}>
          <h2 style={styles.panelTitle}>Preview</h2>
          
          <div 
            style={styles.previewContainer}
            onMouseEnter={() => setIsHoveringPreview(true)}
            onMouseLeave={() => setIsHoveringPreview(false)}
          >
            {isLoading ? (
              <div style={styles.loadingSpinner}>
                <div style={styles.spinner}></div>
                <span>Generating flyer...</span>
              </div>
            ) : previewUrl ? (
              <>
                <img 
                  src={previewUrl} 
                  alt="Generated Flyer" 
                  style={styles.previewImage}
                />
                {isHoveringPreview && (
                  <button
                    style={styles.downloadButton}
                    onClick={handleDownload}
                  >
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

// Styles
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    background: '#1a1a1a',
    padding: '20px',
  },
  content: {
    maxWidth: '1400px',
    margin: '0 auto',
    display: 'flex',
    gap: '30px',
  },
  formPanel: {
    flex: 1,
    maxWidth: '500px',
    background: '#252525',
    borderRadius: '12px',
    padding: '24px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  },
  previewPanel: {
    flex: 1,
    background: '#252525',
    borderRadius: '12px',
    padding: '24px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
  },
  panelTitle: {
    color: '#fff',
    fontSize: '24px',
    fontWeight: 600,
    marginBottom: '24px',
    paddingBottom: '12px',
    borderBottom: '1px solid #333',
  },
  formGroup: {
    marginBottom: '20px',
  },
  label: {
    display: 'block',
    color: '#aaa',
    fontSize: '14px',
    fontWeight: 500,
    marginBottom: '6px',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    background: '#333',
    border: '1px solid #444',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '14px',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  select: {
    width: '100%',
    padding: '10px 14px',
    background: '#333',
    border: '1px solid #444',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '14px',
    boxSizing: 'border-box',
    outline: 'none',
    cursor: 'pointer',
  },
  suggestion: {
    display: 'block',
    color: '#4ade80',
    fontSize: '12px',
    marginTop: '4px',
  },
  previewText: {
    display: 'block',
    color: '#888',
    fontSize: '12px',
    marginTop: '4px',
  },
  timeRow: {
    display: 'flex',
    gap: '12px',
  },
  timeCol: {
    flex: 1,
  },
  timeLabel: {
    display: 'block',
    color: '#888',
    fontSize: '12px',
    marginBottom: '4px',
  },
  fileInputWrapper: {
    position: 'relative',
    overflow: 'hidden',
    display: 'inline-block',
    width: '100%',
  },
  fileInput: {
    position: 'absolute',
    left: 0,
    top: 0,
    opacity: 0,
    width: '100%',
    height: '100%',
    cursor: 'pointer',
  },
  fileInputText: {
    display: 'block',
    padding: '10px 14px',
    background: '#333',
    border: '1px solid #444',
    borderRadius: '8px',
    color: '#888',
    fontSize: '14px',
    textAlign: 'center',
  },
  dividerText: {
    textAlign: 'center',
    color: '#666',
    fontSize: '12px',
    margin: '8px 0',
  },
  error: {
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid #ef4444',
    borderRadius: '8px',
    padding: '12px',
    color: '#ef4444',
    fontSize: '14px',
    marginBottom: '16px',
  },
  buttonRow: {
    display: 'flex',
    gap: '12px',
    marginTop: '24px',
  },
  button: {
    flex: 1,
    padding: '12px 20px',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s',
    border: 'none',
  },
  primaryButton: {
    background: '#3b82f6',
    color: '#fff',
  },
  secondaryButton: {
    background: '#444',
    color: '#fff',
  },
  previewContainer: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    background: '#1a1a1a',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  placeholder: {
    color: '#666',
    textAlign: 'center',
    padding: '40px',
  },
  previewImage: {
    maxWidth: '100%',
    maxHeight: '500px',
    objectFit: 'contain',
  },
  downloadButton: {
    position: 'absolute',
    top: '10px',
    right: '10px',
    padding: '8px 16px',
    background: 'rgba(0,0,0,0.7)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'opacity 0.2s',
  },
  loadingSpinner: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '16px',
    color: '#888',
  },
  spinner: {
    width: '40px',
    height: '40px',
    border: '3px solid #333',
    borderTop: '3px solid #3b82f6',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
};

// Add keyframes for spinner (only once)
if (!document.getElementById('flyer-spinner-styles')) {
  const styleSheet = document.createElement('style');
  styleSheet.id = 'flyer-spinner-styles';
  styleSheet.textContent = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(styleSheet);
}