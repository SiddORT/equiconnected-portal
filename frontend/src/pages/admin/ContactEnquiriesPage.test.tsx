import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import type { ContactEnquiry } from '@/types';
import { ContactEnquiriesPage, ContactEnquiryDetailPage } from './ContactEnquiriesPage';

vi.mock('@/api/admin', () => ({
  getContactEnquiry: vi.fn(),
  listContactEnquiries: vi.fn(),
}));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({ formatTimestamp: (value: string) => `portal time ${value}` }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const enquiry: ContactEnquiry = {
  id: 'enquiry-1',
  name: 'Alex Horse',
  email: 'alex@example.com',
  enquiry_type: 'listing',
  phone: '+971 50 123 4567',
  message: 'I would like to list my practice.',
  submitted_at: '2026-08-21T12:00:00Z',
};

const populatedResponse = {
  data: [enquiry],
  meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
};

const emptyResponse = {
  data: [],
  meta: { page: 1, page_size: 25, total: 0, total_pages: 0 },
};

describe('ContactEnquiriesPage', () => {
  it('shows a populated table with a view action and hides collapsed filter controls', async () => {
    vi.mocked(adminApi.listContactEnquiries).mockResolvedValue(populatedResponse);
    render(<MemoryRouter><ContactEnquiriesPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Contact Enquiries' })).toBeTruthy();
    expect(screen.getByText('Alex Horse')).toBeTruthy();
    expect(screen.getByText('Listing my practice')).toBeTruthy();
    expect(screen.getByText('+971 50 123 4567')).toBeTruthy();
    expect(screen.getByText(`portal time ${enquiry.submitted_at}`)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'View contact enquiry from Alex Horse' }).getAttribute('href'))
      .toBe('/admin/contact-enquiries/enquiry-1');
    expect(screen.queryByLabelText('Submitted from')).toBeNull();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Filters' }));
    expect(screen.getByLabelText('Submitted from')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Filters' }));
    expect(screen.queryByLabelText('Submitted from')).toBeNull();
  });

  it('combines URL filters, requests the selected page, and resets paging when filters change', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listContactEnquiries).mockResolvedValue({
      ...populatedResponse,
      meta: { page: 3, page_size: 25, total: 75, total_pages: 3 },
    });
    render(
      <MemoryRouter initialEntries={[
        '/admin/contact-enquiries?search=horse&enquiry_type=general&date_from=2026-08-01&date_to=2026-08-31&page=3&page_size=25',
      ]}>
        <ContactEnquiriesPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminApi.listContactEnquiries).toHaveBeenLastCalledWith({
      search: 'horse',
      enquiry_type: 'general',
      date_from: '2026-08-01',
      date_to: '2026-08-31',
      page: 3,
      page_size: 25,
    }));
    expect(await screen.findByLabelText('Pagination')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Partnership' }));
    await waitFor(() => expect(adminApi.listContactEnquiries).toHaveBeenLastCalledWith({
      search: 'horse',
      enquiry_type: 'partnership',
      date_from: '2026-08-01',
      date_to: '2026-08-31',
      page: 1,
      page_size: 25,
    }));
  });

  it('updates the request and URL-backed controls for pagination and page size', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listContactEnquiries).mockResolvedValue({
      ...populatedResponse,
      meta: { page: 1, page_size: 25, total: 30, total_pages: 2 },
    });
    render(<MemoryRouter><ContactEnquiriesPage /></MemoryRouter>);

    expect(await screen.findByText('Showing 1 to 25 of 30 entries')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(adminApi.listContactEnquiries).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, page_size: 25 })
    ));

    await user.selectOptions(screen.getByLabelText('Rows per page'), '10');
    await waitFor(() => expect(adminApi.listContactEnquiries).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 10 })
    ));
  });

  it('clears filters and keeps pagination hidden for empty and no-match responses', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.listContactEnquiries).mockImplementation(async (params) =>
      params?.search ? emptyResponse : { ...emptyResponse, meta: { ...emptyResponse.meta, total: 0 } }
    );
    render(<MemoryRouter><ContactEnquiriesPage /></MemoryRouter>);
    expect(await screen.findByText('No contact enquiries yet')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Filters' }));
    await user.click(screen.getByRole('button', { name: 'Partnership' }));
    expect(await screen.findByText('No contact enquiries found')).toBeTruthy();
    expect(screen.queryByLabelText('Pagination')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Clear all filters' }));
    expect(await screen.findByText('No contact enquiries yet')).toBeTruthy();
  });

  it('explains an invalid date range without making an API request', async () => {
    vi.mocked(adminApi.listContactEnquiries).mockResolvedValue(emptyResponse);
    render(
      <MemoryRouter initialEntries={[
        '/admin/contact-enquiries?date_from=2026-09-05&date_to=2026-09-01&page=2',
      ]}>
        <ContactEnquiriesPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText('Submitted from must be on or before submitted to.')).toBeTruthy();
    expect(adminApi.listContactEnquiries).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
  });

  it('offers a retry after a list request fails', async () => {
    vi.mocked(adminApi.listContactEnquiries)
      .mockRejectedValueOnce(new Error('temporary network issue'))
      .mockResolvedValueOnce(populatedResponse);
    render(<MemoryRouter><ContactEnquiriesPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load contact enquiries')).toBeTruthy();
    expect(screen.getByText('Failed to load contact enquiries.')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Alex Horse')).toBeTruthy();
    expect(adminApi.listContactEnquiries).toHaveBeenCalledTimes(2);
  });

  it('ignores an older list result after a newer search returns no matches', async () => {
    let resolveOld!: (value: typeof populatedResponse) => void;
    const oldSearch = new Promise<typeof populatedResponse>((resolve) => { resolveOld = resolve; });
    vi.mocked(adminApi.listContactEnquiries).mockImplementation((params) =>
      params?.search === 'old' ? oldSearch : Promise.resolve(emptyResponse)
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/contact-enquiries?search=old']}>
        <ContactEnquiriesPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminApi.listContactEnquiries).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'old' })
    ));
    const search = screen.getByRole('searchbox', { name: 'Search contact enquiries' });
    await user.clear(search);
    await user.type(search, 'new');
    expect(await screen.findByText('No contact enquiries found')).toBeTruthy();

    await act(async () => {
      resolveOld(populatedResponse);
      await oldSearch;
    });
    expect(screen.getByText('No contact enquiries found')).toBeTruthy();
    expect(screen.queryByText('Alex Horse')).toBeNull();
  });
});

describe('ContactEnquiryDetailPage', () => {
  it('loads complete multiline details, formats time in portal settings, and preserves list state', async () => {
    const fullEnquiry: ContactEnquiry = {
      ...enquiry,
      phone: null,
      message: 'First line of the message.\nSecond line with all of its details.',
    };
    vi.mocked(adminApi.getContactEnquiry).mockResolvedValue(fullEnquiry);
    render(
      <MemoryRouter initialEntries={[
        '/admin/contact-enquiries/enquiry-1?search=horse&enquiry_type=general&page=2&page_size=10',
      ]}>
        <Routes>
          <Route path="/admin/contact-enquiries/:id" element={<ContactEnquiryDetailPage />} />
          <Route path="/admin/contact-enquiries" element={<a href="/admin/contact-enquiries">List destination</a>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'Contact Enquiry' })).toBeTruthy();
    expect(screen.getByText('Alex Horse')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'alex@example.com' }).getAttribute('href'))
      .toBe('mailto:alex@example.com');
    expect(screen.getByText('Not provided')).toBeTruthy();
    expect(screen.getByText(/First line of the message\.\s*Second line with all of its details\./)).toBeTruthy();
    expect(screen.getByText(`portal time ${fullEnquiry.submitted_at}`)).toBeTruthy();
    expect(screen.getByRole('link', { name: '← Back to contact enquiries' }).getAttribute('href'))
      .toBe('/admin/contact-enquiries?search=horse&enquiry_type=general&page=2&page_size=10');
    expect(adminApi.getContactEnquiry).toHaveBeenCalledWith('enquiry-1');
  });

  it('shows a retryable detail error', async () => {
    vi.mocked(adminApi.getContactEnquiry)
      .mockRejectedValueOnce(new Error('not available'))
      .mockResolvedValueOnce(enquiry);
    render(
      <MemoryRouter initialEntries={['/admin/contact-enquiries/enquiry-1']}>
        <Routes>
          <Route path="/admin/contact-enquiries/:id" element={<ContactEnquiryDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Failed to load this contact enquiry.')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('I would like to list my practice.')).toBeTruthy();
  });
});