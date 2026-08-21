import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { MultiEmailField, type EmailEntry } from '@/components/admin/MultiEmailField';
import { MultiPhoneField, type PhoneEntry } from '@/components/admin/MultiPhoneField';
import type { ProviderPortalUpdate } from '@/types';
import styles from './ProviderProfileCollections.module.css';

export type PortalLocation = NonNullable<ProviderPortalUpdate['locations']>[number] & {
  is_primary: boolean;
};
export type PortalPhoto = NonNullable<ProviderPortalUpdate['photos']>[number] & {
  display_order: number;
  is_thumbnail: boolean;
};
export type PortalQualification = NonNullable<ProviderPortalUpdate['qualifications']>[number] & {
  display_order: number;
};

interface ProviderProfileCollectionsProps {
  locations: PortalLocation[];
  onLocationsChange: (locations: PortalLocation[]) => void;
  phones: PhoneEntry[];
  onPhonesChange: (phones: PhoneEntry[]) => void;
  emails: EmailEntry[];
  onEmailsChange: (emails: EmailEntry[]) => void;
  photos: PortalPhoto[];
  onPhotosChange: (photos: PortalPhoto[]) => void;
  qualifications: PortalQualification[];
  onQualificationsChange: (qualifications: PortalQualification[]) => void;
  showQualifications: boolean;
  disabled: boolean;
}

function withPrimary<T extends { is_primary: boolean }>(entries: T[], index: number) {
  return entries.map((entry, entryIndex) => ({ ...entry, is_primary: entryIndex === index }));
}

function withThumbnail(entries: PortalPhoto[], index: number) {
  return entries.map((entry, entryIndex) => ({ ...entry, is_thumbnail: entryIndex === index }));
}

function removeAndPromote<T extends { is_primary: boolean }>(entries: T[], index: number) {
  const removed = entries[index];
  const next = entries.filter((_, entryIndex) => entryIndex !== index);
  if (removed.is_primary && next.length > 0) next[0] = { ...next[0], is_primary: true };
  return next;
}

export function ProviderProfileCollections({
  locations,
  onLocationsChange,
  phones,
  onPhonesChange,
  emails,
  onEmailsChange,
  photos,
  onPhotosChange,
  qualifications,
  onQualificationsChange,
  showQualifications,
  disabled,
}: ProviderProfileCollectionsProps) {
  function updateLocation(index: number, patch: Partial<PortalLocation>) {
    onLocationsChange(locations.map((location, itemIndex) => (
      itemIndex === index ? { ...location, ...patch } : location
    )));
  }

  function updatePhoto(index: number, patch: Partial<PortalPhoto>) {
    onPhotosChange(photos.map((photo, itemIndex) => (
      itemIndex === index ? { ...photo, ...patch } : photo
    )));
  }

  function updateQualification(index: number, patch: Partial<PortalQualification>) {
    onQualificationsChange(qualifications.map((qualification, itemIndex) => (
      itemIndex === index ? { ...qualification, ...patch } : qualification
    )));
  }

  function removePhoto(index: number) {
    const removed = photos[index];
    const next = photos.filter((_, itemIndex) => itemIndex !== index);
    if (removed.is_thumbnail && next.length > 0) {
      next[0] = { ...next[0], is_thumbnail: true };
    }
    onPhotosChange(next.map((photo, itemIndex) => ({ ...photo, display_order: itemIndex })));
  }

  return (
    <>
      <section className={styles.collection} aria-labelledby="portal-locations-heading">
        <div className={styles.collectionHeader}>
          <div>
            <h2 id="portal-locations-heading">Locations</h2>
            <p>Give members a clear address for each place you provide care.</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onLocationsChange([
              ...locations,
              {
                name: null,
                address_line_1: '',
                address_line_2: null,
                city: '',
                state_province: null,
                country: null,
                postal_code: null,
                latitude: null,
                longitude: null,
                is_primary: locations.length === 0,
              },
            ])}
          >
            Add location
          </Button>
        </div>
        {locations.length === 0 && <p className={styles.empty}>No locations added yet.</p>}
        <div className={styles.stack}>
          {locations.map((location, index) => (
            <fieldset className={styles.entry} key={index}>
              <legend>Location {index + 1}</legend>
              <div className={styles.entryActions}>
                <label className={styles.selection}>
                  <input
                    type="radio"
                    name="primary-location"
                    checked={location.is_primary}
                    onChange={() => onLocationsChange(withPrimary(locations, index))}
                    disabled={disabled}
                  />
                  Primary location
                </label>
                <button
                  type="button"
                  className={styles.remove}
                  onClick={() => onLocationsChange(removeAndPromote(locations, index))}
                  disabled={disabled}
                  aria-label={`Remove location ${index + 1}`}
                >
                  Remove
                </button>
              </div>
              <div className={styles.grid}>
                <Input label="Location name" value={location.name ?? ''} onChange={(event) => updateLocation(index, { name: event.target.value || null })} disabled={disabled} />
                <Input label="Address line 1" value={location.address_line_1} onChange={(event) => updateLocation(index, { address_line_1: event.target.value })} disabled={disabled} required />
                <Input label="Address line 2" value={location.address_line_2 ?? ''} onChange={(event) => updateLocation(index, { address_line_2: event.target.value || null })} disabled={disabled} />
                <Input label="City" value={location.city} onChange={(event) => updateLocation(index, { city: event.target.value })} disabled={disabled} required />
                <Input label="State, province, or emirate" value={location.state_province ?? ''} onChange={(event) => updateLocation(index, { state_province: event.target.value || null })} disabled={disabled} />
                <Input label="Country" value={location.country ?? ''} onChange={(event) => updateLocation(index, { country: event.target.value || null })} disabled={disabled} />
                <Input label="Postal code" value={location.postal_code ?? ''} onChange={(event) => updateLocation(index, { postal_code: event.target.value || null })} disabled={disabled} />
                <Input label="Latitude" type="number" value={location.latitude ?? ''} onChange={(event) => updateLocation(index, { latitude: event.target.value ? Number(event.target.value) : null })} disabled={disabled} />
                <Input label="Longitude" type="number" value={location.longitude ?? ''} onChange={(event) => updateLocation(index, { longitude: event.target.value ? Number(event.target.value) : null })} disabled={disabled} />
              </div>
            </fieldset>
          ))}
        </div>
      </section>

      <section className={styles.collection} aria-label="Contact details">
        <div className={styles.collectionHeader}>
          <div>
            <h2>Contact details</h2>
            <p>Choose one main phone number and email address for members.</p>
          </div>
        </div>
        <div className={styles.stack}>
          <MultiPhoneField entries={phones} onChange={onPhonesChange} disabled={disabled} />
          <MultiEmailField entries={emails} onChange={onEmailsChange} disabled={disabled} />
        </div>
      </section>

      <section className={styles.collection} aria-labelledby="portal-photos-heading">
        <div className={styles.collectionHeader}>
          <div>
            <h2 id="portal-photos-heading">Profile photos</h2>
            <p>Add image links, a helpful description, and choose the image members see first.</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onPhotosChange([
              ...photos,
              {
                storage_reference: '',
                alt_text: null,
                caption: null,
                display_order: photos.length,
                is_thumbnail: photos.length === 0,
              },
            ])}
          >
            Add photo
          </Button>
        </div>
        {photos.length === 0 && <p className={styles.empty}>No profile photos added yet.</p>}
        <div className={styles.stack}>
          {photos.map((photo, index) => (
            <fieldset className={styles.entry} key={index}>
              <legend>Photo {index + 1}</legend>
              <div className={styles.entryActions}>
                <label className={styles.selection}>
                  <input
                    type="radio"
                    name="provider-thumbnail"
                    checked={photo.is_thumbnail}
                    onChange={() => onPhotosChange(withThumbnail(photos, index))}
                    disabled={disabled}
                  />
                  Show first
                </label>
                <button type="button" className={styles.remove} onClick={() => removePhoto(index)} disabled={disabled} aria-label={`Remove photo ${index + 1}`}>Remove</button>
              </div>
              <div className={styles.grid}>
                <Input label="Image link" type="url" value={photo.storage_reference} onChange={(event) => updatePhoto(index, { storage_reference: event.target.value })} disabled={disabled} placeholder="https://example.com/photo.jpg" required />
                <Input label="Image description" value={photo.alt_text ?? ''} onChange={(event) => updatePhoto(index, { alt_text: event.target.value || null })} disabled={disabled} placeholder="Describe the image for screen readers" />
                <Input label="Caption" value={photo.caption ?? ''} onChange={(event) => updatePhoto(index, { caption: event.target.value || null })} disabled={disabled} />
              </div>
            </fieldset>
          ))}
        </div>
      </section>

      {showQualifications && (
        <section className={styles.collection} aria-labelledby="portal-qualifications-heading">
          <div className={styles.collectionHeader}>
            <div>
              <h2 id="portal-qualifications-heading">Qualifications</h2>
              <p>List professional qualifications that members should know about.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={() => onQualificationsChange([
                ...qualifications,
                { title: '', institution: null, year_obtained: null, description: null, display_order: qualifications.length },
              ])}
            >
              Add qualification
            </Button>
          </div>
          {qualifications.length === 0 && <p className={styles.empty}>No qualifications added yet.</p>}
          <div className={styles.stack}>
            {qualifications.map((qualification, index) => (
              <fieldset className={styles.entry} key={index}>
                <legend>Qualification {index + 1}</legend>
                <div className={styles.entryActions}>
                  <button type="button" className={styles.remove} onClick={() => onQualificationsChange(qualifications.filter((_, itemIndex) => itemIndex !== index).map((item, itemIndex) => ({ ...item, display_order: itemIndex })))} disabled={disabled} aria-label={`Remove qualification ${index + 1}`}>Remove</button>
                </div>
                <div className={styles.grid}>
                  <Input label="Qualification" value={qualification.title} onChange={(event) => updateQualification(index, { title: event.target.value })} disabled={disabled} required />
                  <Input label="Institution" value={qualification.institution ?? ''} onChange={(event) => updateQualification(index, { institution: event.target.value || null })} disabled={disabled} />
                  <Input label="Year obtained" type="number" min="1900" max="2100" value={qualification.year_obtained ?? ''} onChange={(event) => updateQualification(index, { year_obtained: event.target.value ? Number(event.target.value) : null })} disabled={disabled} />
                  <label className={styles.description}>Description
                    <textarea value={qualification.description ?? ''} onChange={(event) => updateQualification(index, { description: event.target.value || null })} disabled={disabled} rows={3} />
                  </label>
                </div>
              </fieldset>
            ))}
          </div>
        </section>
      )}
    </>
  );
}