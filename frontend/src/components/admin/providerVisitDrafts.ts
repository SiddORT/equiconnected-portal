import type { DoctorVisit, DoctorVisitCreate } from '@/types';

export interface VisitDraft extends DoctorVisitCreate {
  key: string;
  id?: string;
}

// Local date matches the calendar controls; the server remains authoritative
// about whether a saved visit is still upcoming at save time.
export function todayDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export function visitPayload(visit: DoctorVisitCreate): DoctorVisitCreate {
  const location = visit.location;
  return {
    start_date: visit.start_date,
    end_date: visit.end_date,
    location: {
      ...location,
      address_line_1: location.address_line_1.trim(),
      city: location.city.trim(),
      name: location.name?.trim() || null,
      address_line_2: location.address_line_2?.trim() || null,
      state_province: location.state_province?.trim() || null,
      country: location.country?.trim() || null,
      postal_code: location.postal_code?.trim() || null,
      latitude: location.latitude === '' || location.latitude == null ? null : Number(location.latitude),
      longitude: location.longitude === '' || location.longitude == null ? null : Number(location.longitude),
    },
  };
}

export function sameVisit(a: DoctorVisitCreate, b: DoctorVisitCreate) {
  const left = visitPayload(a);
  const right = visitPayload(b);
  return left.start_date === right.start_date && left.end_date === right.end_date &&
    (['name', 'address_line_1', 'address_line_2', 'city', 'state_province', 'country', 'postal_code', 'latitude', 'longitude'] as const)
      .every((key) => left.location[key] === right.location[key]);
}

export function orderVisitDrafts(drafts: VisitDraft[], saved: DoctorVisit[]): VisitDraft[] | null {
  const pending = [...drafts];
  let calendar = [...saved];
  const ordered: VisitDraft[] = [];
  while (pending.length) {
    const index = pending.findIndex((draft) => !calendar.some((visit) =>
      visit.id !== draft.id && visit.start_date <= draft.end_date && draft.start_date <= visit.end_date));
    if (index < 0) return null;
    const [draft] = pending.splice(index, 1);
    ordered.push(draft);
    calendar = [...calendar.filter((visit) => visit.id !== draft.id), { ...draft, id: draft.id ?? draft.key }];
  }
  return ordered;
}

export function validateVisitDrafts(drafts: VisitDraft[], saved: DoctorVisit[]): string | null {
  const effective = [...saved.filter((v) => !drafts.some((draft) => draft.id === v.id)), ...drafts];
  for (const draft of drafts) {
    if (!draft.start_date || !draft.end_date || !draft.location.address_line_1.trim() || !draft.location.city.trim())
      return 'Complete the address, city and both dates for each staged visit, or discard that change.';
    if (draft.end_date < draft.start_date) return 'Visit end date must be on or after start date.';
    const original = draft.id ? saved.find((v) => v.id === draft.id) : null;
    if (draft.id && (!original || original.start_date <= todayDate()))
      return 'A visit that has already started cannot be amended.';
    for (const key of ['latitude', 'longitude'] as const) {
      const coordinate = draft.location[key];
      if (coordinate != null && coordinate !== '' && (!Number.isFinite(Number(coordinate)) || Math.abs(Number(coordinate)) > (key === 'latitude' ? 90 : 180)))
        return `Visit ${key} is outside the allowed range.`;
    }
    if (effective.some((other) => other !== draft && other.start_date <= draft.end_date && draft.start_date <= other.end_date))
      return 'Visit dates cannot overlap, including shared start or end dates.';
  }
  if (!orderVisitDrafts(drafts, saved))
    return 'These amendments would overlap recorded dates while being saved. Adjust the dates so each amendment can be saved without an overlap.';
  return null;
}

export function visitSummary(visit: DoctorVisitCreate) {
  return `${visit.start_date} to ${visit.end_date} · ${[
    visit.location.name, visit.location.address_line_1, visit.location.address_line_2,
    visit.location.city, visit.location.state_province, visit.location.country, visit.location.postal_code,
  ].filter(Boolean).join(', ')}`;
}
