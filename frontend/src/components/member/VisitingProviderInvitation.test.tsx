import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { getMemberVisitAvailability } from '@/api/providers';
import { VisitingProviderInvitation } from './VisitingProviderInvitation';

vi.mock('@/api/providers', () => ({ getMemberVisitAvailability: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const show = () => render(<MemoryRouter><VisitingProviderInvitation query="name=Maple&saved=true&region=Dubai" /></MemoryRouter>);

it('discovers future-only visits without applying directory filters and preserves the return query', async () => {
  vi.mocked(getMemberVisitAvailability).mockResolvedValue({ has_visits: true });
  show();
  expect(await screen.findByText('See our esteemed visiting providers')).toBeTruthy();
  expect(screen.getByRole('link', { name: /View calendar/ }).getAttribute('href')).toBe('/providers/visiting-calendar?name=Maple&saved=true&region=Dubai');
  expect(getMemberVisitAvailability).toHaveBeenCalledWith();
  expect(screen.getByText(/independent of your filters/)).toBeTruthy();
});

it('only declares no visits after a successful empty response', async () => {
  vi.mocked(getMemberVisitAvailability).mockResolvedValue({ has_visits: false });
  show();
  expect(screen.queryByText('No providers visiting')).toBeNull();
  expect(screen.getByRole('status')).toBeTruthy();
  expect(await screen.findByText('No providers visiting')).toBeTruthy();
  expect(screen.queryByRole('link', { name: /View calendar/ })).toBeNull();
});

it('keeps a failed check distinct from empty and allows retry', async () => {
  vi.mocked(getMemberVisitAvailability).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ has_visits: true });
  show();
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.queryByText('No providers visiting')).toBeNull();
  await userEvent.setup().click(screen.getByRole('button', { name: 'Retry visiting providers' }));
  expect(await screen.findByRole('link', { name: /View calendar/ })).toBeTruthy();
});

it('ignores responses after unmount', async () => {
  let finish!: (value: { has_visits: boolean }) => void;
  vi.mocked(getMemberVisitAvailability).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const view = show();
  view.unmount();
  finish({ has_visits: false });
  await waitFor(() => expect(screen.queryByText('No providers visiting')).toBeNull());
});