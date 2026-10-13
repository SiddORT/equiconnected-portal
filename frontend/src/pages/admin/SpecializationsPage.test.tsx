import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as specializationsApi from '@/api/specializations';
import type { PaginatedResponse, Specialization } from '@/types';
import { SpecializationsPage } from './SpecializationsPage';

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn(),
  createSpecialization: vi.fn(),
  updateSpecialization: vi.fn(),
  setSpecializationStatus: vi.fn(),
  confirmImport: vi.fn(),
  downloadImportTemplate: vi.fn(),
  exportSpecializations: vi.fn(),
  previewImport: vi.fn(),
}));

const specialization: Specialization = {
  id: 'specialization-1',
  name: 'Equine dentistry',
  description: null,
  is_active: true,
  created_at: '2026-10-13T00:00:00Z',
  updated_at: '2026-10-13T00:00:00Z',
};

function response(data: Specialization[]): PaginatedResponse<Specialization> {
  return {
    data,
    meta: { page: 1, page_size: 10, total: data.length, total_pages: data.length ? 1 : 0 },
  };
}

function expectNoFooter() {
  expect(screen.queryByLabelText('Pagination')).toBeNull();
  expect(screen.queryByLabelText('Rows per page')).toBeNull();
  expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
  expect(screen.queryByRole('button', { name: /Previous/ })).toBeNull();
  expect(screen.queryByRole('button', { name: /Next/ })).toBeNull();
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('SpecializationsPage empty table controls', () => {
  it('hides the entire footer when no specializations exist', async () => {
    vi.mocked(specializationsApi.listSpecializations).mockResolvedValue(response([]));
    render(<MemoryRouter><SpecializationsPage /></MemoryRouter>);

    expect(await screen.findByText('No specializations yet')).toBeTruthy();
    expectNoFooter();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Add specialization/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Import/ })).toBeTruthy();
  });

  it('hides controls for empty filtered results and restores them when records return', async () => {
    vi.mocked(specializationsApi.listSpecializations)
      .mockResolvedValueOnce(response([specialization]))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([specialization]));
    const event = userEvent.setup();
    render(<MemoryRouter><SpecializationsPage /></MemoryRouter>);

    expect(await screen.findByText(specialization.name)).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    await event.click(screen.getByRole('button', { name: 'Inactive' }));
    expect(await screen.findByText('No results found')).toBeTruthy();
    expectNoFooter();
    expect(specializationsApi.listSpecializations).toHaveBeenLastCalledWith(
      expect.objectContaining({ is_active: false, page: 1 }),
    );

    await event.click(screen.getByRole('button', { name: 'All' }));
    expect(await screen.findByText(specialization.name)).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
  });

  it('keeps the normal footer and page-size behavior when data exists', async () => {
    vi.mocked(specializationsApi.listSpecializations).mockResolvedValue(response([specialization]));
    const event = userEvent.setup();
    render(<MemoryRouter><SpecializationsPage /></MemoryRouter>);

    expect(await screen.findByText(specialization.name)).toBeTruthy();
    expect(screen.getByText('Showing 1 to 1 of 1 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Previous/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Next/ })).toBeTruthy();
    await event.selectOptions(screen.getByLabelText('Rows per page'), '25');
    await waitFor(() => expect(specializationsApi.listSpecializations).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 25 }),
    ));
  });
});
