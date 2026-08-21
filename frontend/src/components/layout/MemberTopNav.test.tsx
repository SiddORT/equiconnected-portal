import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { MemberTopNav } from './MemberTopNav';

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'member-id',
      email: 'rider@example.com',
      first_name: 'Amina',
      last_name: 'Rider',
      full_name: 'Amina Rider',
      role: 'horse_owner',
      roles: ['horse_owner'],
      email_verified_at: '2026-08-21T00:00:00Z',
      is_active: true,
    },
    logout: vi.fn(),
  }),
}));

afterEach(cleanup);

describe('MemberTopNav', () => {
  it('provides member navigation and a visible logout control', () => {
    render(<MemoryRouter><MemberTopNav /></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Browse providers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Your profile' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Log out' })).toBeTruthy();
  });
});