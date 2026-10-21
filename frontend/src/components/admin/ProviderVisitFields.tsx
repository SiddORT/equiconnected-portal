import type { DoctorVisitCreate } from '@/types';
import { Input } from '@/components/ui/Input';
import styles from './ProviderForm.module.css';

export function ProviderVisitFields({ value, onChange }: {
  value: DoctorVisitCreate;
  onChange: (value: DoctorVisitCreate) => void;
}) {
  function locationField(key: keyof DoctorVisitCreate['location'], text: string) {
    onChange({ ...value, location: { ...value.location, [key]: text } });
  }
  return (
    <div className={styles.grid}>
      <Input label="Location name" value={value.location.name ?? ''} maxLength={200} onChange={(e) => locationField('name', e.target.value)} />
      <Input label="Address line 1" value={value.location.address_line_1} maxLength={300} required onChange={(e) => locationField('address_line_1', e.target.value)} />
      <Input label="Address line 2" value={value.location.address_line_2 ?? ''} maxLength={300} onChange={(e) => locationField('address_line_2', e.target.value)} />
      <Input label="City" value={value.location.city} maxLength={150} required onChange={(e) => locationField('city', e.target.value)} />
      <Input label="State / Province" value={value.location.state_province ?? ''} maxLength={150} onChange={(e) => locationField('state_province', e.target.value)} />
      <Input label="Country" value={value.location.country ?? ''} maxLength={150} onChange={(e) => locationField('country', e.target.value)} />
      <Input label="Postal code" value={value.location.postal_code ?? ''} maxLength={30} onChange={(e) => locationField('postal_code', e.target.value)} />
      <Input label="Latitude" type="number" step="any" min={-90} max={90} value={value.location.latitude ?? ''} onChange={(e) => locationField('latitude', e.target.value)} />
      <Input label="Longitude" type="number" step="any" min={-180} max={180} value={value.location.longitude ?? ''} onChange={(e) => locationField('longitude', e.target.value)} />
      <Input label="Start date" type="date" value={value.start_date} required onChange={(e) => onChange({ ...value, start_date: e.target.value })} />
      <Input label="End date" type="date" min={value.start_date || undefined} value={value.end_date} required onChange={(e) => onChange({ ...value, end_date: e.target.value })} />
    </div>
  );
}
