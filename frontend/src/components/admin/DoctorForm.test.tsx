import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readFileSync } from 'node:fs';
import { DoctorForm, type DoctorInvitationFormConfig } from './DoctorForm';
import type { InvitationDraftProvider } from '@/types';
import { listProviderSignupLanguages } from '@/api/auth';

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

vi.mock('@/api/auth', () => ({
  listProviderSignupLanguages: vi.fn().mockResolvedValue([
    { id: 'lang-en', name: 'English', code: 'en' },
    { id: 'lang-fr', name: 'French', code: 'fr' },
  ]),
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
    recipientEmail: 'invited-doctor@example.com',
    emailsEdited: false,
    loadSpecializations: vi.fn().mockResolvedValue([]),
    onSaveDraft,
    onSubmit,
  };
}

async function fillInvitationCredentials(user: ReturnType<typeof userEvent.setup>) {
  const password = screen.getByLabelText('Password') as HTMLInputElement;
  const confirmation = screen.getByLabelText('Confirm password') as HTMLInputElement;
  if (!password.value) await user.type(password, 'SecureHorse7');
  if (!confirmation.value) await user.type(confirmation, 'SecureHorse7');
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('starts with the doctor invitation recipient and lets the doctor add another email', async () => {
  const onSaveDraft = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<DoctorForm invitation={invitationConfig(onSaveDraft)} />);
  expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value)
    .toBe('invited-doctor@example.com');
  await user.click(screen.getByRole('button', { name: /Add email/i }));
  await user.type(screen.getByRole('textbox', { name: 'Email address 2' }), 'office@example.com');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
    expect.objectContaining({
      emails: [
        { email: 'invited-doctor@example.com', is_primary: true },
        { email: 'office@example.com', is_primary: false },
      ],
    })
  ));
});

it('selects invitation languages from the public catalog, saves, restores, and submits them', async () => {
  const save = vi.fn().mockResolvedValue(undefined);
  const submit = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  const config = invitationConfig(save, submit);
  config.initial = { ...invitationDoctor, language_ids: ['lang-fr'] };
  const { unmount } = render(<DoctorForm invitation={config} />);

  await waitFor(() => expect(listProviderSignupLanguages).toHaveBeenCalled());
  expect(screen.getByRole('button', { name: 'Remove French' })).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'Languages' }));
  expect(screen.getByRole('option', { name: /French/ }).getAttribute('aria-selected')).toBe('true');
  await user.click(screen.getByRole('option', { name: /French/ }));
  await user.click(screen.getByRole('button', { name: 'Select all' }));
  expect(screen.getByRole('option', { name: /English/ }).getAttribute('aria-selected')).toBe('true');
  expect(screen.getByRole('option', { name: /French/ }).getAttribute('aria-selected')).toBe('true');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
    language_ids: ['lang-en', 'lang-fr'],
  })));
  expect(save.mock.calls[0][0]).not.toHaveProperty('password');
  expect(save.mock.calls[0][0]).not.toHaveProperty('password_confirmation');

  unmount();
  const savedIds = save.mock.calls[0][0].language_ids;
  const reopened = invitationConfig(save, submit);
  reopened.initial = { ...invitationDoctor, language_ids: savedIds };
  render(<DoctorForm invitation={reopened} />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Remove English' })).toBeTruthy());
  expect(screen.getByRole('button', { name: 'Remove French' })).toBeTruthy();
  await user.type(screen.getByLabelText('First name'), 'Avery');
  await user.type(screen.getByLabelText('Last name'), 'Quinn');
  await fillInvitationCredentials(user);
  await user.click(screen.getByRole('button', { name: 'Submit for review' }));
  await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({
    language_ids: ['lang-en', 'lang-fr'],
  })));
});

it('shows a public language-catalog error without dropping previously saved ids', async () => {
  vi.mocked(listProviderSignupLanguages).mockRejectedValueOnce(new Error('Catalog unavailable'));
  const save = vi.fn().mockResolvedValue(undefined);
  const config = invitationConfig(save);
  config.initial = { ...invitationDoctor, language_ids: ['retired-language'] };
  const user = userEvent.setup();
  render(<DoctorForm invitation={config} />);

  expect(await screen.findByText('Failed to load languages.')).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
    language_ids: ['retired-language'],
  })));
});

describe('DoctorForm invitation services', () => {
  it('selects all specializations while filtered without losing individual selections', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(save);
    config.loadSpecializations = vi.fn().mockResolvedValue(
      Array.from({ length: 8 }, (_, i) => ({ id: `spec-${i}`, name: i === 0 ? 'Dental' : `Care ${i}` }))
    );
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);
    await screen.findByRole('button', { name: 'Dental' });
    await user.type(screen.getByPlaceholderText('Filter specializations…'), 'Dental');
    await user.click(screen.getByRole('button', { name: 'Select all specializations' }));
    await user.click(screen.getByRole('button', { name: /Dental/ }));
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      specialization_ids: Array.from({ length: 7 }, (_, i) => `spec-${i + 1}`),
    })));
  });
  it('restores stable visit choice and includes its radius in saved drafts', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    const config = invitationConfig(onSaveDraft);
    config.initial = {
      ...invitationDoctor,
      visit_stability: 'STABLE_VISIT',
      maximum_working_radius_km: 45,
    };
    render(<DoctorForm invitation={config} />);

    expect((screen.getByRole('checkbox', { name: 'Offers stable visits' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole('spinbutton', { name: 'Maximum working radius (km)' }) as HTMLInputElement).value).toBe('45');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(expect.objectContaining({
      visit_stability: 'STABLE_VISIT',
      maximum_working_radius_km: 45,
    })));
  });

  it('requires a positive stable-visit radius and submits the selected enum', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<DoctorForm invitation={invitationConfig(undefined, onSubmit)} />);
    await user.click(screen.getByRole('checkbox', { name: 'Offers stable visits' }));
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a finite radius greater than 0 km.')).toBeTruthy();
    await user.type(screen.getByRole('spinbutton', { name: 'Maximum working radius (km)' }), '90');
    await user.type(screen.getByLabelText('First name'), 'Avery');
    await user.type(screen.getByLabelText('Last name'), 'Quinn');
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      visit_stability: 'STABLE_VISIT',
      maximum_working_radius_km: 90,
    })));
  });

  it('restores emergency dial/local number and requires a valid number', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(undefined, onSubmit);
    config.initial = {
      ...invitationDoctor,
      emergency_services_available: true,
      emergency_contact_number: '+44 2071234567',
    };
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);

    expect((screen.getByRole('textbox', { name: 'Emergency contact number' }) as HTMLInputElement).value).toBe('2071234567');
    await user.clear(screen.getByRole('textbox', { name: 'Emergency contact number' }));
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a valid emergency number with 6–15 digits.')).toBeTruthy();
  });

  it('clears the emergency phone when emergency services are switched off', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(onSaveDraft);
    config.initial = {
      ...invitationDoctor,
      emergency_services_available: true,
      emergency_contact_number: '+44 2071234567',
    };
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);
    await user.click(screen.getByRole('checkbox', { name: 'Emergency services available' }));
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(expect.objectContaining({
      emergency_services_available: false,
      emergency_contact_number: null,
    })));
  });

  it('starts with one optional address, keeps field order and saves one completed location', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<DoctorForm invitation={invitationConfig(onSaveDraft)} />);
    const address = screen.getByRole('group', { name: 'Practice address' });
    const labels = Array.from(address.querySelectorAll('label')).map((label) => label.textContent?.trim());
    expect(labels).toEqual(['Location name', 'Postal / ZIP code', 'Country', 'State / province', 'City', 'Address line 1', 'Address line 2']);
    expect(screen.queryByRole('button', { name: /Add address|Remove address/i })).toBeNull();
    const css = readFileSync('src/components/invite/InvitationProfileFields.module.css', 'utf8');
    expect(css).toMatch(/\.firstRow\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
    expect(css).toMatch(/\.placeRow\s*\{\s*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
    expect(css).toMatch(/@media \(max-width: 680px\)\s*\{[\s\S]*\.firstRow, \.placeRow \{ grid-template-columns: minmax\(0, 1fr\)/);
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenLastCalledWith(expect.objectContaining({ locations: [] })));
    await user.type(screen.getByRole('textbox', { name: 'Location name' }), 'Main clinic');
    await user.type(screen.getByRole('textbox', { name: 'Address line 1' }), '4 Clinic Road');
    await user.type(screen.getByRole('textbox', { name: 'City' }), 'Austin');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenLastCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({
        name: 'Main clinic',
        address_line_1: '4 Clinic Road',
        city: 'Austin',
        is_primary: true,
      })],
    })));
  });

  it('requires an explicit legacy address choice before draft save or submit', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const submit = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(save, submit);
    config.initial = { ...invitationDoctor, locations: [
      { name: 'North', address_line_1: '1 North Rd', city: 'Calgary', is_primary: true },
      { name: 'South', address_line_1: '2 South Rd', city: 'Austin', is_primary: false },
    ] };
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);
    expect(screen.queryByLabelText('Location name')).toBeNull();
    expect(screen.getByRole('button', { name: /Keep North/ })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(save).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByText('Choose one saved address to keep before continuing.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Keep South/ }));
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Austin');
    await user.click(screen.getByRole('button', { name: /Keep North/ }));
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Calgary');
    await user.click(screen.getByRole('button', { name: /Keep South/ }));
    await user.type(screen.getByLabelText('First name'), 'Avery');
    await user.type(screen.getByLabelText('Last name'), 'Quinn');
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'South', is_primary: true })],
    })));
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'South', is_primary: true })],
    })));
  });

  it('restores and submits named addresses without adding organization associations', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(undefined, onSubmit);
    config.initial = {
      ...invitationDoctor,
      first_name: 'Avery',
      last_name: 'Quinn',
      locations: [{
        name: 'North Clinic',
        address_line_1: '12 Stable Road',
        address_line_2: null,
        city: 'Calgary',
        state_province: 'Alberta',
        country: 'Canada',
        postal_code: 'T2P 1J9',
        is_primary: true,
      }],
    };
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);
  expect(screen.getByText('invited-doctor@example.com', { selector: 'strong' })).toBeTruthy();
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({
        name: 'North Clinic',
        address_line_1: '12 Stable Road',
        city: 'Calgary',
        is_primary: true,
      })],
    })));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      password: 'SecureHorse7',
      password_confirmation: 'SecureHorse7',
    });
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('organization_ids');
  });

  it('preserves selected specializations hidden by the filter', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const config = invitationConfig(onSaveDraft);
    const names = ['Cardiology', 'Dentistry', 'Dermatology', 'Emergency', 'Equine surgery',
      'Internal medicine', 'Neurology', 'Ophthalmology', 'Radiology'];
    const specs = names.map((name, index) => ({ id: `spec-${index}`, name }));
    config.initial = { ...invitationDoctor, specialization_ids: ['spec-8'] };
    config.loadSpecializations = vi.fn().mockResolvedValue(specs);
    const user = userEvent.setup();
    render(<DoctorForm invitation={config} />);
    const filter = await screen.findByPlaceholderText('Filter specializations…');
    await user.type(filter, 'Cardiology');
    expect(screen.getByText(/selected not shown/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(expect.objectContaining({
      specialization_ids: ['spec-8'],
    })));
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