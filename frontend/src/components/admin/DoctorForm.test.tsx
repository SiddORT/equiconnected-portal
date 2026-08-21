import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DoctorForm, type DoctorInvitationFormConfig } from './DoctorForm';
import type { InvitationDraftProvider } from '@/types';

vi.mock('@/api/doctors', () => ({
  addDoctorSpecialization: vi.fn(),
  createDoctor: vi.fn(),
  getDoctor: vi.fn(),
  removeDoctorSpecialization: vi.fn(),
  updateDoctor: vi.fn(),
  updateDoctorPublication: vi.fn(),
  updateDoctorStatus: vi.fn(),
}));

vi.mock('@/api/providers', () => ({
  addProviderEmail: vi.fn(),
  addProviderPhone: vi.fn(),
  removeProviderEmail: vi.fn(),
  removeProviderPhone: vi.fn(),
}));

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn().mockResolvedValue({
    data: [],
    meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

const invitationDoctor: InvitationDraftProvider = {
  name: 'Dr. Avery Quinn',
  description: null,
  email: null,
  phone: null,
  website: null,
  visit_stability: 'NOT_STABLE_VISIT',
  status: 'ACTIVE',
  specialization_ids: [],
  locations: [],
  phones: [],
  emails: [],
  photos: [],
  professional_title: null,
  biography: null,
  years_experience: null,
  experience_description: null,
};

function invitationConfig(
  onSaveDraft: DoctorInvitationFormConfig['onSaveDraft'] = vi.fn().mockResolvedValue(undefined),
  onSubmit: DoctorInvitationFormConfig['onSubmit'] = vi.fn().mockResolvedValue(undefined),
): DoctorInvitationFormConfig {
  return {
    initial: invitationDoctor,
    loadSpecializations: vi.fn().mockResolvedValue([]),
    onSaveDraft,
    onSubmit,
  };
}

afterEach(cleanup);

describe('DoctorForm visit stability', () => {
  it('uses Yes and No labels for restored invitation values', () => {
    render(<DoctorForm invitation={invitationConfig()} />);

    const select = screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => [option.text, option.value])).toEqual([
      ['Select…', ''],
      ['Yes', 'STABLE_VISIT'],
      ['No', 'NOT_STABLE_VISIT'],
    ]);
    expect(select.value).toBe('NOT_STABLE_VISIT');
    expect(screen.getByRole('option', { name: 'No', selected: true })).toBeTruthy();
  });

  it('keeps enum values in doctor invitation draft-save and submit payloads', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<DoctorForm invitation={invitationConfig(onSaveDraft, onSubmit)} />);

    const select = screen.getByRole('combobox', { name: 'Visit Stable' });
    await user.selectOptions(select, 'STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'STABLE_VISIT' })
    ));

    await user.selectOptions(select, 'NOT_STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'NOT_STABLE_VISIT' })
    ));
  });

  it('keeps Stable and Not stable labels in administrator mode', async () => {
    render(<DoctorForm />);

    const select = screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    expect(Array.from(select.options).map((option) => option.text)).toEqual([
      'Select…',
      'Stable',
      'Not stable',
    ]);
  });
});