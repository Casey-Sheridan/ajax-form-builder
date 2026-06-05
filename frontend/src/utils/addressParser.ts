// US state/territory abbreviations for validation
const US_STATES = new Set([
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
  'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
  'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
  'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
  'DC','PR','GU','VI','AS','MP',
]);

// "NY" or "NY 10001" or "NY 10001-4567"
const STATE_ONLY_RE = /^([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?$/i;

// "New York NY 10001" — city + state + optional zip with no comma between them
const CITY_STATE_RE = /^(.+?)\s+([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?$/i;

/**
 * Parses a single US address string into a logical two-line form.
 *
 * Line 1: street number + street name + optional unit
 * Line 2: City, ST ZIP  (normalized with comma + space before state)
 *
 * Handles:
 *   "123 Main St, New York, NY 10001"          → ["123 Main St", "New York, NY 10001"]
 *   "123 Main St, Apt 4, New York, NY 10001"   → ["123 Main St, Apt 4", "New York, NY 10001"]
 *   "123 Main St, New York NY 10001"           → ["123 Main St", "New York, NY 10001"]
 *   "123 Main St, New York, NY"                → ["123 Main St", "New York, NY"]
 *   "123 Main St Apt 4B, New York, NY 10001"   → ["123 Main St Apt 4B", "New York, NY 10001"]
 *
 * Falls back to first-comma split when the address doesn't match any known pattern.
 */
export function parseUSAddress(addr: string): [string, string] {
  const trimmed = addr.trim();
  if (!trimmed) return ['', ''];

  const parts = trimmed.split(',').map(p => p.trim()).filter(Boolean);
  if (parts.length < 2) return [trimmed, ''];

  const last = parts[parts.length - 1];

  // Case 1: last comma-part is "STATE [ZIP]"
  // e.g. "123 Main St, Apt 4, New York, NY 10001" → last="NY 10001"
  const stateOnlyMatch = last.match(STATE_ONLY_RE);
  if (stateOnlyMatch) {
    const state = stateOnlyMatch[1].toUpperCase();
    if (US_STATES.has(state) && parts.length >= 3) {
      const zip = stateOnlyMatch[2] ?? '';
      const city = parts[parts.length - 2];
      const streetParts = parts.slice(0, parts.length - 2);
      const line2 = zip ? `${city}, ${state} ${zip}` : `${city}, ${state}`;
      return [streetParts.join(', '), line2];
    }
  }

  // Case 2: last comma-part contains city+state inline
  // e.g. "123 Main St, New York NY 10001" → last="New York NY 10001"
  const cityStateMatch = last.match(CITY_STATE_RE);
  if (cityStateMatch) {
    const state = cityStateMatch[2].toUpperCase();
    if (US_STATES.has(state)) {
      const city = cityStateMatch[1];
      const zip = cityStateMatch[3] ?? '';
      const streetParts = parts.slice(0, parts.length - 1);
      const line2 = zip ? `${city}, ${state} ${zip}` : `${city}, ${state}`;
      return [streetParts.join(', '), line2];
    }
  }

  // Fallback: split on first comma
  return [parts[0], parts.slice(1).join(', ')];
}

/**
 * Expands a single raw address into all three render-payload variants so
 * template elements can bind to whichever key they need:
 *
 *   expandAddressField("venue_address", "123 Main St, Springfield, IL 62701")
 *   → {
 *       venue_address:  "123 Main St, Springfield, IL 62701",
 *       venue_address1: "123 Main St",
 *       venue_address2: "Springfield, IL 62701",
 *     }
 */
export function expandAddressField(key: string, raw: string): Record<string, string> {
  const [line1, line2] = parseUSAddress(raw);
  return {
    [key]: [line1, line2].filter(Boolean).join(', '),
    [`${key}1`]: line1,
    [`${key}2`]: line2,
  };
}
