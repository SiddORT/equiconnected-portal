/**
 * OrganizationAssociation — doctor invitation section for linking the doctor
 * to existing hospital/clinic organizations, or requesting a new one.
 *
 * Selection is kept locally (chips) and persisted as PENDING relationships
 * when the invitation is submitted.
 */
import { useEffect, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import { requestNewOrganization, searchOrganizations, getOrgSuggestions } from '@/api/invitations';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { SearchInput } from '@/components/ui/SearchInput';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import type { OrgRequestResult, OrgSearchResult, OrgSuggestion } from '@/types';
import styles from './OrganizationAssociation.module.css';

const TYPE_OPTIONS = [
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
];

interface OrganizationAssociationProps {
  token: string;
  selected: OrgSearchResult[];
  onChange: (orgs: OrgSearchResult[]) => void;
}

export function OrganizationAssociation({ token, selected, onChange }: OrganizationAssociationProps) {
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [results, setResults] = useState<OrgSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showNewOrgForm, setShowNewOrgForm] = useState(false);
  const [submittedRequests, setSubmittedRequests] = useState<OrgRequestResult[]>([]);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setSearchError(null);
      return;
    }
    let cancelled = false;
    setSearching(true);
    (async () => {
      try {
        const res = await searchOrganizations(
          query.trim(),
          (typeFilter || undefined) as 'HOSPITAL' | 'CLINIC' | undefined
        );
        if (!cancelled) {
          setResults(res.data);
          setSearchError(null);
        }
      } catch (err) {
        if (!cancelled) setSearchError(extractErrorMessage(err, 'Search failed. Please try again.'));
      } finally {
        if (!cancelled) setSearching(false);
      }
    })();
    return () => { cancelled = true; };
  }, [query, typeFilter]);

  function addOrg(org: OrgSearchResult) {
    if (!selected.some((o) => o.id === org.id)) onChange([...selected, org]);
  }

  function removeOrg(id: string) {
    onChange(selected.filter((o) => o.id !== id));
  }

  return (
    <Card padding="lg" shadow="sm" className={styles.cardFull}>
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>
          Organization association <span className={styles.optionalTag}>— optional</span>
        </h3>
        <p className={styles.hint}>
          Link yourself to the hospitals or clinics where you practice. Associations are
          created when you submit and will show as pending until reviewed.
        </p>

        {selected.length > 0 && (
          <div className={styles.chipRow} aria-label="Selected organizations">
            {selected.map((org) => (
              <span key={org.id} className={styles.chip}>
                {org.name}
                <span className={styles.chipMeta}>{org.provider_type === 'HOSPITAL' ? 'Hospital' : 'Clinic'}</span>
                <button
                  type="button"
                  className={styles.chipRemove}
                  onClick={() => removeOrg(org.id)}
                  aria-label={`Remove ${org.name}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div className={styles.searchRow}>
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search hospitals and clinics…"
            aria-label="Search organizations"
            containerClassName={styles.searchInput}
          />
          <Select
            aria-label="Filter by type"
            options={TYPE_OPTIONS}
            placeholder="All types"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            containerClassName={styles.typeSelect}
          />
        </div>

        {searching && (
          <div className={styles.searchStatus}><LoadingSpinner size="sm" /> Searching…</div>
        )}
        {searchError && <p className={styles.error} role="alert">{searchError}</p>}
        {!searching && !searchError && query.trim() && results.length === 0 && (
          <p className={styles.hint}>No matching organizations found.</p>
        )}
        {results.length > 0 && (
          <ul className={styles.resultList}>
            {results.map((org) => {
              const isSelected = selected.some((o) => o.id === org.id);
              return (
                <li key={org.id} className={styles.resultItem}>
                  <div>
                    <span className={styles.resultName}>{org.name}</span>
                    <span className={styles.resultMeta}>
                      {org.provider_type === 'HOSPITAL' ? 'Hospital' : 'Clinic'}
                      {org.city ? ` · ${org.city}` : ''}
                    </span>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={isSelected ? 'ghost' : 'outline'}
                    disabled={isSelected}
                    onClick={() => addOrg(org)}
                  >
                    {isSelected ? 'Selected' : 'Select'}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}

        {submittedRequests.length > 0 && (
          <div className={styles.requestList}>
            {submittedRequests.map((req) => (
              <p key={req.id} className={styles.requestNote} role="status">
                ✓ New organization request submitted for “{req.organization_name}” — our team
                will review it.
              </p>
            ))}
          </div>
        )}

        {!showNewOrgForm ? (
          <button
            type="button"
            className={styles.revealLink}
            onClick={() => setShowNewOrgForm(true)}
          >
            Can't find your Hospital/Clinic?
          </button>
        ) : (
          <NewOrgRequestForm
            token={token}
            onSelectExisting={(org) => {
              addOrg(org);
              setShowNewOrgForm(false);
            }}
            onRequested={(req) => {
              setSubmittedRequests((prev) => [...prev, req]);
              setShowNewOrgForm(false);
            }}
            onCancel={() => setShowNewOrgForm(false)}
          />
        )}
      </section>
    </Card>
  );
}

// ── New organization request sub-form ────────────────────────────────────────

interface NewOrgRequestFormProps {
  token: string;
  onSelectExisting: (org: OrgSearchResult) => void;
  onRequested: (request: OrgRequestResult) => void;
  onCancel: () => void;
}

function NewOrgRequestForm({ token, onSelectExisting, onRequested, onCancel }: NewOrgRequestFormProps) {
  const [orgName, setOrgName] = useState('');
  const [orgType, setOrgType] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [locationHint, setLocationHint] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<OrgSuggestion[] | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(confirmNoMatch: boolean) {
    const errs: Record<string, string> = {};
    if (!orgName.trim()) errs.organization_name = 'Organization name is required.';
    if (!orgType) errs.organization_type = 'Type is required.';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setApiError(null);
    setSubmitting(true);
    try {
      const req = await requestNewOrganization(token, {
        organization_name: orgName.trim(),
        organization_type: orgType as 'HOSPITAL' | 'CLINIC',
        contact_email: contactEmail.trim() || null,
        location_hint: locationHint.trim() || null,
        confirm_no_match: confirmNoMatch,
      });
      setSuggestions(null);
      onRequested(req);
    } catch (err) {
      const suggested = getOrgSuggestions(err);
      if (suggested) {
        setSuggestions(suggested);
      } else {
        setApiError(extractErrorMessage(err, 'Failed to submit the request. Please try again.'));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.newOrgForm}>
      <h4 className={styles.newOrgTitle}>Request a new organization</h4>
      {apiError && <p className={styles.error} role="alert">{apiError}</p>}
      <div className={styles.newOrgGrid}>
        <Input
          label="Organization name"
          value={orgName}
          onChange={(e) => { setOrgName(e.target.value); setSuggestions(null); }}
          error={errors.organization_name}
          required
          maxLength={300}
        />
        <Select
          label="Type"
          options={TYPE_OPTIONS}
          placeholder="Select type…"
          value={orgType}
          onChange={(e) => { setOrgType(e.target.value); setSuggestions(null); }}
          error={errors.organization_type}
          required
        />
        <Input
          label="Contact email"
          type="email"
          value={contactEmail}
          onChange={(e) => setContactEmail(e.target.value)}
          hint="Optional"
        />
        <Input
          label="Location hint"
          placeholder="e.g. Lexington, KY"
          value={locationHint}
          onChange={(e) => setLocationHint(e.target.value)}
          hint="Optional"
          maxLength={500}
        />
      </div>

      {suggestions && suggestions.length > 0 && (
        <div className={styles.suggestions} role="alert">
          <p className={styles.suggestionsTitle}>Did you mean one of these existing organizations?</p>
          <ul className={styles.suggestionList}>
            {suggestions.map((s) => (
              <li key={s.id} className={styles.suggestionCard}>
                <div>
                  <span className={styles.resultName}>{s.name}</span>
                  <span className={styles.resultMeta}>{s.type === 'HOSPITAL' ? 'Hospital' : 'Clinic'}</span>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    onSelectExisting({ id: s.id, name: s.name, provider_type: s.type, city: null })
                  }
                >
                  Select this org
                </Button>
              </li>
            ))}
          </ul>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            loading={submitting}
            onClick={() => submit(true)}
          >
            None of these — submit my request anyway
          </Button>
        </div>
      )}

      <div className={styles.newOrgActions}>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        {!suggestions && (
          <Button type="button" variant="primary" size="sm" loading={submitting} onClick={() => submit(false)}>
            Submit request
          </Button>
        )}
      </div>
    </div>
  );
}
