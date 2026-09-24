import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TimeSettingsProvider } from '@/app/TimeSettingsContext';
import { ProviderDetailPage } from './ProviderDetailPage';
import { getProvider, updateProviderVisit } from '@/api/providers';
import type { Provider } from '@/types';

vi.mock('@/api/providers', () => ({
  addProviderSpecialization: vi.fn(),
  createProviderLocation: vi.fn(),
  createProviderVisit: vi.fn(),
  deleteProviderLocation: vi.fn(),
  deleteProviderPhoto: vi.fn(),
  getProvider: vi.fn(),
  removeProviderSpecialization: vi.fn(),
  setProviderThumbnail: vi.fn(),
  updateProviderLocation: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
  updateProviderVisit: vi.fn(),
  uploadProviderPhoto: vi.fn(),
}));

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn().mockResolvedValue({
    data: [], meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

function doctor(overrides: Partial<Provider> = {}): Provider {
  return {
    id: 'provider-1', provider_type: 'DOCTOR', name: 'Prairie Equine Care',
    description: null, website: null, email: null, phone: null,
    visit_stability: 'NOT_STABLE_VISIT', status: 'ACTIVE', publication_status: 'UNPUBLISHED',
    specializations: [], languages: [], locations: [], photos: [], phones: [], emails: [],
    qualifications: [], thumbnail_url: null, doctor_profile: null,
    maximum_working_radius_km: null, clinic_hospital_visit: false,
    emergency_services_available: false, emergency_contact_name: null, emergency_contact_number: null,
    doctor_availability: 'VISITING', doctor_visits: [], ...overrides,
  } as Provider;
}

function renderDetail() {
  return render(
    <TimeSettingsProvider>
      <MemoryRouter initialEntries={['/admin/providers/provider-1']}>
        <Routes>
          <Route path="/admin/providers/:id" element={<ProviderDetailPage />} />
        </Routes>
      </MemoryRouter>
    </TimeSettingsProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ProviderDetailPage doctor visits', () => {
  it('shows the exact empty visiting state and reloads after amending an upcoming trip', async () => {
    const empty = doctor();
    const upcoming = {
      id: 'visit-1',
      location: {
        address_line_1: '1 Prairie Way', city: 'Calgary', name: 'North paddock',
        state_province: 'Alberta', country: 'Canada', postal_code: 'T2P 1J9',
      },
      start_date: '2999-06-01', end_date: '2999-06-03',
    };
    const refreshed = doctor({ doctor_visits: [{ ...upcoming, location: { ...upcoming.location, address_line_1: '2 Prairie Way' } }] });
    vi.mocked(getProvider).mockResolvedValueOnce(empty).mockResolvedValueOnce(refreshed);
    vi.mocked(updateProviderVisit).mockResolvedValue(refreshed);

    renderDetail();
    expect(await screen.findByText('No visit scheduled yet')).toBeTruthy();

    // Simulate the provider returning an upcoming period after a first refresh.
    vi.mocked(getProvider).mockResolvedValueOnce(refreshed);
    await waitFor(() => expect(getProvider).toHaveBeenCalledTimes(1));
    // Reload through the page's existing retry-safe data path by remounting.
    cleanup();
    renderDetail();
    expect(await screen.findByText(/Upcoming · 2999-06-01 to 2999-06-03/)).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Amend' }));
    const address = screen.getByLabelText('Address line 1') as HTMLInputElement;
    await userEvent.setup().clear(address);
    await userEvent.setup().type(address, '2 Prairie Way');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Save amendment' }));

    await waitFor(() => expect(updateProviderVisit).toHaveBeenCalledWith('provider-1', 'visit-1', expect.objectContaining({
      start_date: '2999-06-01',
      end_date: '2999-06-03',
      location: expect.objectContaining({ address_line_1: '2 Prairie Way', city: 'Calgary' }),
    })));
    await waitFor(() => expect(getProvider).toHaveBeenCalledTimes(3));
    expect(await screen.findByText(/2 Prairie Way, Calgary/)).toBeTruthy();
  });
});