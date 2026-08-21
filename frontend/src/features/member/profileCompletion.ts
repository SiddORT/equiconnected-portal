import { getStateOptions } from '@/utils/geography';
import type { MemberProfile, StableProfile } from '@/types';

export type ProfileSectionId = 'personal' | 'stable' | 'horses';

export interface ProfileCompletionSection {
  id: ProfileSectionId;
  label: string;
  complete: boolean;
  completedItems: number;
  totalItems: number;
  missing: string[];
  nextAction: string | null;
}

export interface ProfileCompletion {
  percentage: number;
  completedItems: number;
  totalItems: number;
  isComplete: boolean;
  nextSection: ProfileSectionId | null;
  nextAction: string | null;
  sections: ProfileCompletionSection[];
}

function hasValue(value: string | null | undefined): boolean {
  return Boolean(value?.trim());
}

function stateIsApplicable(country: string | null | undefined): boolean {
  return Boolean(country && getStateOptions(country).length > 0);
}

function section(
  id: ProfileSectionId,
  label: string,
  items: Array<{ complete: boolean; missing: string }>,
): ProfileCompletionSection {
  const missing = items.filter((item) => !item.complete).map((item) => item.missing);
  return {
    id,
    label,
    complete: missing.length === 0,
    completedItems: items.length - missing.length,
    totalItems: items.length,
    missing,
    nextAction: missing[0] ?? null,
  };
}

function personalSection(profile: MemberProfile): ProfileCompletionSection {
  const needsState = stateIsApplicable(profile.country);
  const items = [
    { complete: hasValue(profile.first_name), missing: 'Add your first name.' },
    { complete: hasValue(profile.last_name), missing: 'Add your last name.' },
    { complete: hasValue(profile.mobile_number), missing: 'Add your mobile number.' },
    { complete: hasValue(profile.address), missing: 'Add your personal address.' },
    { complete: hasValue(profile.country), missing: 'Choose your country.' },
    ...(needsState
      ? [{ complete: hasValue(profile.state_province), missing: 'Choose your state or province.' }]
      : []),
    { complete: hasValue(profile.city), missing: 'Choose your city.' },
    { complete: hasValue(profile.postal_code), missing: 'Add your postal or ZIP code.' },
  ];
  return section('personal', 'Account and contact', items);
}

function stableSection(stable: StableProfile | null): ProfileCompletionSection {
  const country = stable?.country;
  const items = [
    { complete: hasValue(stable?.name), missing: 'Add your stable name.' },
    { complete: hasValue(stable?.address), missing: 'Add the stable address.' },
    { complete: hasValue(country), missing: 'Choose the stable country.' },
    ...(stateIsApplicable(country)
      ? [{ complete: hasValue(stable?.state_province), missing: 'Choose the stable state or province.' }]
      : []),
    { complete: hasValue(stable?.city), missing: 'Choose the stable city.' },
    { complete: hasValue(stable?.postal_code), missing: 'Add the stable postal or ZIP code.' },
    { complete: hasValue(stable?.contact_name), missing: 'Add a stable contact name.' },
    { complete: hasValue(stable?.contact_phone), missing: 'Add a stable contact phone.' },
    { complete: hasValue(stable?.contact_email), missing: 'Add a stable contact email.' },
  ];
  return section('stable', 'Stable Manager', items);
}

function horseSection(profile: MemberProfile): ProfileCompletionSection {
  const hasRequiredHorse = profile.horses.some(
    (horse) => hasValue(horse.name) && hasValue(horse.sex),
  );
  return section('horses', 'Horse Owner', [
    { complete: hasRequiredHorse, missing: 'Add at least one horse with a name and sex.' },
  ]);
}

export function calculateProfileCompletion(profile: MemberProfile): ProfileCompletion {
  const sections = [personalSection(profile)];
  const roles = new Set(profile.roles.map((role) => role.toLowerCase()));
  if (roles.has('stable_manager')) sections.push(stableSection(profile.stable_profile));
  if (roles.has('horse_owner')) sections.push(horseSection(profile));

  const completedItems = sections.reduce((total, item) => total + item.completedItems, 0);
  const totalItems = sections.reduce((total, item) => total + item.totalItems, 0);
  const next = sections.find((item) => !item.complete);
  return {
    percentage: totalItems === 0 ? 100 : Math.round((completedItems / totalItems) * 100),
    completedItems,
    totalItems,
    isComplete: !next,
    nextSection: next?.id ?? null,
    nextAction: next?.nextAction ?? null,
    sections,
  };
}