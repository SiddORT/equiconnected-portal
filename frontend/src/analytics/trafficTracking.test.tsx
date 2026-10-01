import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { useState } from 'react';

const { publicGet, publicPost, memberPost } = vi.hoisted(() => ({
  publicGet: vi.fn(),
  publicPost: vi.fn(),
  memberPost: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({ get: publicGet, post: publicPost })),
    isAxiosError: vi.fn((error: unknown) => (
      typeof error === 'object' && error !== null && 'isAxiosError' in error
    )),
  },
}));

vi.mock('@/api/client', () => ({
  apiClient: { post: memberPost },
}));

import { recordMemberTrafficView, usePublicTrafficRoute } from './trafficTracking';

function HomeRoute() {
  usePublicTrafficRoute('home', '/');
  return null;
}

function RerenderableHomeRoute() {
  const [count, setCount] = useState(0);
  usePublicTrafficRoute('home', '/');
  return <button onClick={() => setCount((value) => value + 1)}>Rerender {count}</button>;
}

describe('traffic route instrumentation', () => {
  beforeEach(() => {
    localStorage.clear();
    publicGet.mockReset().mockResolvedValue({ data: { timezone: 'UTC' } });
    publicPost.mockReset().mockResolvedValue(undefined);
    memberPost.mockReset().mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('is Strict Mode safe and ignores query/hash-only route changes', async () => {
    const router = createMemoryRouter(
      [{ path: '*', element: <HomeRoute /> }],
      { initialEntries: ['/'] },
    );
    render(<StrictMode><RouterProvider router={router} /></StrictMode>);

    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(1));
    const firstPayload = publicPost.mock.calls[0][1];
    expect(publicPost.mock.calls[0][0]).toBe('/public/traffic/page-view');
    expect(firstPayload).toMatchObject({
      category: 'home',
      first_eligible_view_today: true,
    });
    expect(firstPayload.navigation_key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(Object.keys(firstPayload).sort()).toEqual([
      'category',
      'first_eligible_view_today',
      'navigation_key',
    ]);
    expect(publicGet).toHaveBeenCalledWith('/system-settings', { timeout: 2500 });
    expect(localStorage.getItem('equiconnected-traffic-visitor-day')).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    await router.navigate('/?provider_type=DOCTOR');
    await router.navigate('/#care');
    expect(publicPost).toHaveBeenCalledTimes(1);

    await router.navigate('/not-eligible');
    await router.navigate('/');
    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(2));
    expect(publicPost.mock.calls[1][1].first_eligible_view_today).toBe(false);
  });

  it('retries a failed send with the exact same idempotency key', async () => {
    publicPost
      .mockRejectedValueOnce(new Error('temporary network issue'))
      .mockResolvedValueOnce(undefined);
    const router = createMemoryRouter(
      [{ path: '*', element: <HomeRoute /> }],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);

    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(2));
    expect(publicPost.mock.calls[0][1]).toEqual(publicPost.mock.calls[1][1]);
  });

  it('ignores rerenders but counts same-route navigation and refresh as new page views', async () => {
    const router = createMemoryRouter(
      [{ path: '*', element: <RerenderableHomeRoute /> }],
      { initialEntries: ['/'] },
    );
    const firstMount = render(<RouterProvider router={router} />);
    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'Rerender 0' }));
    expect(screen.getByRole('button', { name: 'Rerender 1' })).toBeTruthy();
    expect(publicPost).toHaveBeenCalledTimes(1);

    await router.navigate('/');
    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(2));
    firstMount.unmount();

    const refreshedRouter = createMemoryRouter(
      [{ path: '*', element: <HomeRoute /> }],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={refreshedRouter} />);
    await waitFor(() => expect(publicPost).toHaveBeenCalledTimes(3));
    expect(new Set(publicPost.mock.calls.map(([, payload]) => payload.navigation_key)).size).toBe(3);
    expect(publicPost.mock.calls.map(([, payload]) => payload.first_eligible_view_today))
      .toEqual([true, false, false]);
  });

  it('does not count URLs carrying token-like query or fragment parameters', async () => {
    const router = createMemoryRouter(
      [{ path: '*', element: <HomeRoute /> }],
      { initialEntries: ['/?access_token=secret'] },
    );
    render(<RouterProvider router={router} />);
    await router.navigate('/#verification_token=secret');
    await router.navigate('/?code=secret');
    expect(publicPost).not.toHaveBeenCalled();
    expect(publicGet).not.toHaveBeenCalled();
  });

  it('sends provider popularity only through the authorized member endpoint', async () => {
    recordMemberTrafficView('provider_profile', 'provider-uuid');
    recordMemberTrafficView('provider_directory', 'not-allowed');
    await waitFor(() => expect(memberPost).toHaveBeenCalledTimes(1));
    expect(memberPost).toHaveBeenCalledWith('/member/providers/traffic-view', {
      category: 'provider_profile',
      navigation_key: expect.any(String),
      first_eligible_view_today: true,
      provider_id: 'provider-uuid',
    }, { timeout: 2500 });
    expect(publicPost).not.toHaveBeenCalled();
  });
});