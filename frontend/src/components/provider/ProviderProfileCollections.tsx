import { useEffect, useRef, useState } from 'react';
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
  onUploadPhoto: (item: { file: File; alt_text: string | null; caption: string | null }) => Promise<PortalPhoto>;
  qualifications: PortalQualification[];
  onQualificationsChange: (qualifications: PortalQualification[]) => void;
  showQualifications: boolean;
  disabled: boolean;
}

interface StagedPhoto {
  id: string;
  file: File;
  preview: string;
  alt_text: string;
  caption: string;
}

const IMAGE_ACCEPT = 'image/jpeg,image/png,image/gif,image/webp';
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;

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
  onUploadPhoto,
  qualifications,
  onQualificationsChange,
  showQualifications,
  disabled,
}: ProviderProfileCollectionsProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stagedPhotosRef = useRef<StagedPhoto[]>([]);
  const [stagedPhotos, setStagedPhotos] = useState<StagedPhoto[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);

  useEffect(() => {
    stagedPhotosRef.current = stagedPhotos;
  }, [stagedPhotos]);

  useEffect(() => () => {
    stagedPhotosRef.current.forEach((photo) => URL.revokeObjectURL(photo.preview));
  }, []);

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

  function addPhotos(files: FileList) {
    const additions: StagedPhoto[] = [];
    for (const file of Array.from(files)) {
      if (!IMAGE_ACCEPT.split(',').includes(file.type)) {
        setUploadError('Choose a JPEG, PNG, GIF, or WebP image.');
        continue;
      }
      if (file.size > MAX_IMAGE_SIZE) {
        setUploadError('Each image must be 10 MB or smaller.');
        continue;
      }
      additions.push({
        id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
        preview: URL.createObjectURL(file),
        alt_text: '',
        caption: '',
      });
    }
    if (additions.length > 0) {
      setUploadError(null);
      setStagedPhotos((current) => [...current, ...additions]);
    }
  }

  function updateStagedPhoto(id: string, patch: Partial<Pick<StagedPhoto, 'alt_text' | 'caption'>>) {
    setStagedPhotos((current) => current.map((photo) => (
      photo.id === id ? { ...photo, ...patch } : photo
    )));
  }

  function removeStagedPhoto(id: string) {
    setStagedPhotos((current) => {
      const removed = current.find((photo) => photo.id === id);
      if (removed) URL.revokeObjectURL(removed.preview);
      return current.filter((photo) => photo.id !== id);
    });
  }

  async function uploadStagedPhotos() {
    if (!stagedPhotos.length || uploadingPhotos) return;
    const completedIds: string[] = [];
    try {
      setUploadError(null);
      setUploadingPhotos(true);
      for (const photo of stagedPhotos) {
        await onUploadPhoto({
          file: photo.file,
          alt_text: photo.alt_text.trim() || null,
          caption: photo.caption.trim() || null,
        });
        completedIds.push(photo.id);
      }
      setStagedPhotos((current) => {
        current
          .filter((photo) => completedIds.includes(photo.id))
          .forEach((photo) => URL.revokeObjectURL(photo.preview));
        return current.filter((photo) => !completedIds.includes(photo.id));
      });
    } catch (error) {
      setStagedPhotos((current) => {
        current
          .filter((photo) => completedIds.includes(photo.id))
          .forEach((photo) => URL.revokeObjectURL(photo.preview));
        return current.filter((photo) => !completedIds.includes(photo.id));
      });
      setUploadError(error instanceof Error ? error.message : 'Photos could not be uploaded. Please try again.');
    } finally {
      setUploadingPhotos(false);
    }
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
            disabled={disabled || uploadingPhotos}
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
            <p>Upload photos, add accessible Alt text and an optional image title, then choose the image members see first.</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => fileInputRef.current?.click()}
          >
            Add photos
          </Button>
        </div>
        <input
          ref={fileInputRef}
          className={styles.fileInput}
          type="file"
          accept={IMAGE_ACCEPT}
          multiple
          onChange={(event) => {
            if (event.target.files) addPhotos(event.target.files);
            event.target.value = '';
          }}
        />
        <div
          className={styles.dropZone}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            addPhotos(event.dataTransfer.files);
          }}
        >
          <span className={styles.dropIcon} aria-hidden="true">🖼</span>
          <span>Drag photos here or use “Add photos”.</span>
          <small>JPEG, PNG, GIF, or WebP · up to 10 MB each</small>
        </div>
        {uploadError && <p className={styles.uploadError} role="alert">{uploadError}</p>}
        {stagedPhotos.length > 0 && (
          <div className={styles.stagedList}>
            {stagedPhotos.map((photo) => (
              <div className={styles.stagedPhoto} key={photo.id}>
                <img src={photo.preview} alt="" className={styles.preview} />
                <div className={styles.stagedFields}>
                  <strong>{photo.file.name}</strong>
                  <Input label="Alt text" value={photo.alt_text} onChange={(event) => updateStagedPhoto(photo.id, { alt_text: event.target.value })} disabled={disabled || uploadingPhotos} placeholder="Describe the image for screen readers" />
                  <Input label="Image title" value={photo.caption} onChange={(event) => updateStagedPhoto(photo.id, { caption: event.target.value })} disabled={disabled || uploadingPhotos} placeholder="Optional title or caption" />
                </div>
                <button type="button" className={styles.remove} onClick={() => removeStagedPhoto(photo.id)} disabled={disabled || uploadingPhotos} aria-label={`Remove ${photo.file.name}`}>Remove</button>
              </div>
            ))}
            <Button type="button" size="sm" disabled={disabled || uploadingPhotos || stagedPhotos.length === 0} onClick={() => void uploadStagedPhotos()}>
              Upload {stagedPhotos.length === 1 ? 'photo' : `${stagedPhotos.length} photos`}
            </Button>
          </div>
        )}
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
              <div className={styles.savedPhoto}>
                {photo.storage_reference ? (
                  <img src={photo.storage_reference} alt={photo.alt_text ?? photo.caption ?? 'Provider photo'} className={styles.preview} />
                ) : (
                  <div className={styles.previewPlaceholder}>Image unavailable</div>
                )}
                <div className={styles.grid}>
                  <Input label="Alt text" value={photo.alt_text ?? ''} onChange={(event) => updatePhoto(index, { alt_text: event.target.value || null })} disabled={disabled} placeholder="Describe the image for screen readers" />
                  <Input label="Image title" value={photo.caption ?? ''} onChange={(event) => updatePhoto(index, { caption: event.target.value || null })} disabled={disabled} placeholder="Optional title or caption" />
                </div>
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
                  <Input label="Title" value={qualification.title} onChange={(event) => updateQualification(index, { title: event.target.value })} disabled={disabled} placeholder="e.g. MBBS, MD, Fellowship…" required />
                  <Input label="Institution" value={qualification.institution ?? ''} onChange={(event) => updateQualification(index, { institution: event.target.value || null })} disabled={disabled} />
                  <Input label="Year obtained" type="number" min="1900" max="2100" value={qualification.year_obtained ?? ''} onChange={(event) => updateQualification(index, { year_obtained: event.target.value ? Number(event.target.value) : null })} disabled={disabled} />
                  <Input label="Description" value={qualification.description ?? ''} onChange={(event) => updateQualification(index, { description: event.target.value || null })} disabled={disabled} maxLength={2000} />
                </div>
              </fieldset>
            ))}
          </div>
        </section>
      )}
    </>
  );
}