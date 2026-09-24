import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProviderForm, type InvitationFormConfig } from './ProviderForm';
import type { InvitationDraftProvider } from '@/types';
import { createProvider, uploadProviderPhoto } from '@/api/providers';

vi.mock('@/api/providers', () => ({
  addProviderEmail: vi.fn(),
  addProviderPhone: vi.fn(),
  addProviderSpecialization: vi.fn(),
  createProvider: vi.fn(),
  createProviderLocation: vi.fn(),
  getProvider: vi.fn(),
  removeProviderEmail: vi.fn(),
  removeProviderPhone: vi.fn(),
  removeProviderSpecialization: vi.fn(),
  updateProvider: vi.fn(),
  updateProviderLocation: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
  uploadProviderPhoto: vi.fn(),
}));

vi.mock('@/api/doctors', () => ({
  addDoctorQualification: vi.fn(),
  updateDoctorQualification: vi.fn(),
  deleteDoctorQualification: vi.fn(),
}));

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn().mockResolvedValue({
    data: [],
    meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

vi.mock('@/api/languages', () => ({
  listLanguages: vi.fn().mockResolvedValue({
    data: [{ id: 'lang-en', name: 'English', code: 'en', is_active: true }],
    meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

const invitationProvider: InvitationDraftProvider = {
  name: 'Cedar Ridge Clinic',
  description: 'Equine care',
  email: null,
  phone: null,
  website: null,
  visit_stability: 'STABLE_VISIT',
  status: 'ACTIVE',
  specialization_ids: [],
  locations: [],
  phones: [],
  emails: [],
  photos: [],
};

function invitationConfig(
  overrides: Partial<InvitationDraftProvider> = {},
  onSaveDraft: InvitationFormConfig['onSaveDraft'] = vi.fn().mockResolvedValue(undefined),
  onSubmit: InvitationFormConfig['onSubmit'] = vi.fn().mockResolvedValue(undefined),
): InvitationFormConfig {
  return {
    providerType: 'CLINIC',
    initial: { ...invitationProvider, ...overrides },
    loadSpecializations: vi.fn().mockResolvedValue([]),
    onSaveDraft,
    onSubmit,
  };
}

afterEach(cleanup);

describe('ProviderForm visit stability', () => {
  it('uses Yes and No labels in invitation mode while preserving enum values and saved selection', () => {
    render(<ProviderForm invitation={invitationConfig()} />);

    const select = screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => [option.text, option.value])).toEqual([
      ['Select…', ''],
      ['Yes', 'STABLE_VISIT'],
      ['No', 'NOT_STABLE_VISIT'],
    ]);
    expect(select.value).toBe('STABLE_VISIT');
  });

  it('restores a saved non-stable invitation selection as No', () => {
    render(
      <ProviderForm
        invitation={invitationConfig({ visit_stability: 'NOT_STABLE_VISIT' })}
      />
    );

    expect(
      (screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement).value
    ).toBe('NOT_STABLE_VISIT');
    expect(screen.getByRole('option', { name: 'No', selected: true })).toBeTruthy();
  });

  it('keeps enum values in draft-save and submit payloads', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <ProviderForm
        invitation={invitationConfig({}, onSaveDraft, onSubmit)}
      />
    );

    const select = screen.getByRole('combobox', { name: 'Visit Stable' });
    await user.selectOptions(select, 'NOT_STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'NOT_STABLE_VISIT' })
    ));

    await user.selectOptions(select, 'STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'STABLE_VISIT' })
    ));
  });

  it('shows Yes and No for stable visits in administrator mode', async () => {
    render(<ProviderForm />);

    const select = screen.getByRole('combobox', { name: 'Stable visit' }) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    expect(Array.from(select.options).map((option) => option.text)).toEqual([
      'Select…',
      'Yes',
      'No',
    ]);
  });

  it('does not render admin-only controls in invitation mode', () => {
    render(<ProviderForm invitation={invitationConfig()} />);
    expect(screen.queryByLabelText('First name')).toBeNull();
    expect(screen.queryByLabelText('Last name')).toBeNull();
    expect(screen.queryByText('Languages')).toBeNull();
    expect(screen.queryByLabelText('Profile photo')).toBeNull();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
  });

  it('shows and requires a positive radius only for stable administrator visits', async () => {
    render(<ProviderForm />);
    const visit = screen.getByRole('combobox', { name: 'Stable visit' });
    await waitFor(() => expect(visit).toBeTruthy());
    const user = userEvent.setup();
    await user.selectOptions(visit, 'STABLE_VISIT');
    const radius = screen.getByLabelText('Maximum working radius (km)') as HTMLInputElement;
    expect(radius.required).toBe(true);
    expect(radius.min).toBe('0.01');
    await user.selectOptions(visit, 'NOT_STABLE_VISIT');
    expect(screen.queryByLabelText('Maximum working radius (km)')).toBeNull();
  });

  it('blocks a new admin provider when email, location, and stable radius are missing', async () => {
    const user = userEvent.setup();
    render(<ProviderForm />);
    await user.type(screen.getByLabelText('Provider / practice name'), 'North Star');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Stable visit' }), 'STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    expect(createProvider).not.toHaveBeenCalled();
    expect(screen.getByText('A primary email is required.')).toBeTruthy();
    expect(screen.getByText('Country is required.')).toBeTruthy();
    expect(screen.getByText('City is required.')).toBeTruthy();
    expect(screen.getByText('Address is required.')).toBeTruthy();
    expect(screen.getByText('A finite radius greater than 0 is required for stable visits.')).toBeTruthy();
  });

  it('only shows emergency fields after emergency services is enabled', async () => {
    const user = userEvent.setup();
    render(<ProviderForm />);
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    await user.click(screen.getByLabelText('Emergency services available'));
    expect(screen.getByLabelText('Emergency contact name')).toBeTruthy();
    expect(screen.getByLabelText('Emergency contact number')).toBeTruthy();
  });

  it('renders the language master option and selection control for admin forms', async () => {
    render(<ProviderForm />);
    await waitFor(() => expect(screen.getByRole('button', { name: /English/ })).toBeTruthy());
    expect(screen.getByLabelText('Search languages')).toBeTruthy();
  });
});