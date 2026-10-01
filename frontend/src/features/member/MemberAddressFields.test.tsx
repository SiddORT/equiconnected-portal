import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as authApi from '@/api/auth';
import { MemberAddressFields, type MemberAddressValue } from './MemberAddressFields';
import { getCountryOptions, getStateOptions } from '@/utils/geography';

vi.mock('@/api/auth', () => ({
  lookupProviderPostalCode: vi.fn(),
}));

const completeCandidate = {
  country: 'United States',
  country_code: 'US',
  state_province: 'Texas',
  city: 'Austin',
  postal_code: '78701',
  display_name: 'Austin, Texas, United States',
};

function AddressHarness({
  section = 'personal',
  initial = {},
}: {
  section?: 'personal' | 'stable';
  initial?: MemberAddressValue;
}) {
  const [value, setValue] = useState<MemberAddressValue>(initial);
  return <MemberAddressFields section={section} value={value}
    onChange={(patch) => setValue((current) => ({ ...current, ...patch }))} />;
}

async function lookup(postalCode = '78701') {
  fireEvent.change(screen.getByLabelText('Pincode / Postal code'), { target: { value: postalCode } });
  await act(async () => { await vi.advanceTimersByTimeAsync(550); });
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe('MemberAddressFields', () => {
  it('does not look up a saved pincode and orders fields for keyboard navigation', async () => {
    const user = userEvent.setup();
    render(<AddressHarness initial={{ postal_code: '78701', country: 'United States', city: 'Austin' }} />);

    expect(authApi.lookupProviderPostalCode).not.toHaveBeenCalled();
    const postal = screen.getByLabelText('Pincode / Postal code');
    const country = screen.getByLabelText('Country');
    expect(postal.compareDocumentPosition(country) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(country.compareDocumentPosition(screen.getByLabelText('Address line 1')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByLabelText('Address line 2')).toBeTruthy();

    postal.focus();
    await user.tab();
    expect(document.activeElement).toBe(country);
    expect(authApi.lookupProviderPostalCode).not.toHaveBeenCalled();
  });

  it('automatically fills a unique complete match after pincode-first lookup', async () => {
    vi.useFakeTimers();
    vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [completeCandidate],
    });
    render(<AddressHarness />);

    await lookup();
    expect(authApi.lookupProviderPostalCode).toHaveBeenCalledWith(
      '78701', expect.any(AbortSignal),
    );
    expect((screen.getByLabelText('Country') as HTMLInputElement).value).toBe('United States');
    expect((screen.getByLabelText('State / Province') as HTMLInputElement).value).toBe('Texas');
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Austin');
    expect(screen.getByRole('status').textContent).toContain('filled');
  });

  it('requires an explicit place choice when a pincode is ambiguous', async () => {
    vi.useFakeTimers();
    vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [
        completeCandidate,
        { ...completeCandidate, city: 'Houston', display_name: 'Houston, Texas, United States' },
      ],
    });
    render(<AddressHarness />);
    await lookup();

    const place = screen.getByLabelText('Matching place for personal location');
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('');
    fireEvent.change(place, { target: { value: '2' } });
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Houston');
    expect(screen.getByRole('status').textContent).toContain('selected');
  });

  it('requires explicit choice for a unique match with an incomplete required state', async () => {
    vi.useFakeTimers();
    vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [{ ...completeCandidate, state_province: '' }],
    });
    render(<AddressHarness />);
    await lookup();

    expect(screen.getByLabelText('Matching place for personal location')).toBeTruthy();
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('');
  });

  it('auto-fills a complete match for a country without state or province choices', async () => {
    vi.useFakeTimers();
    const countryWithoutStates = getCountryOptions()
      .find((option) => getStateOptions(option.value).length === 0)!;
    vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [{
        country: countryWithoutStates.value,
        country_code: '',
        state_province: '',
        city: 'Central',
        postal_code: '1000',
        display_name: `Central, ${countryWithoutStates.value}`,
      }],
    });
    render(<AddressHarness />);
    await lookup('1000');

    expect((screen.getByLabelText('Country') as HTMLInputElement).value).toBe(countryWithoutStates.value);
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Central');
    expect(screen.queryByLabelText('Matching place for personal location')).toBeNull();
  });

  it.each([
    ['no_match', { status: 'no_match', candidates: [] }, 'No complete matching place'],
    ['unavailable', { status: 'unavailable', candidates: [] }, 'lookup is unavailable'],
    ['request rejection', new Error('network error'), 'lookup is unavailable'],
  ])('surfaces manual-entry guidance for %s', async (_label, response, expectedMessage) => {
    vi.useFakeTimers();
    if (response instanceof Error) {
      vi.mocked(authApi.lookupProviderPostalCode).mockRejectedValue(response);
    } else {
      vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue(response as {
        status: 'no_match' | 'unavailable'; candidates: [];
      });
    }
    render(<AddressHarness />);
    await lookup();
    expect(screen.getByRole('status').textContent).toContain(expectedMessage);
    expect(screen.getByLabelText('Country')).toBeTruthy();
    expect(screen.getByLabelText('City')).toBeTruthy();
  });

  it('ignores a stale pincode response after a newer lookup has completed', async () => {
    vi.useFakeTimers();
    let resolveFirst!: (result: { status: 'match'; candidates: typeof completeCandidate[] }) => void;
    vi.mocked(authApi.lookupProviderPostalCode)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({
        status: 'match', candidates: [{ ...completeCandidate, city: 'Houston' }],
      });
    render(<AddressHarness />);

    await lookup('11111');
    fireEvent.change(screen.getByLabelText('Pincode / Postal code'), { target: { value: '22222' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(550); });
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Houston');
    await act(async () => {
      resolveFirst({ status: 'match', candidates: [completeCandidate] });
    });
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Houston');
  });

  it('cancels lookup results when a member corrects location manually', async () => {
    vi.useFakeTimers();
    let resolveLookup!: (result: { status: 'match'; candidates: typeof completeCandidate[] }) => void;
    vi.mocked(authApi.lookupProviderPostalCode).mockImplementation(
      () => new Promise((resolve) => { resolveLookup = resolve; }),
    );
    render(<AddressHarness />);
    await lookup();
    fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Manual city' } });
    await act(async () => {
      resolveLookup({ status: 'match', candidates: [completeCandidate] });
    });

    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Manual city');
    expect(screen.getByRole('status').textContent).toContain('correct location details manually');
  });

  it('keeps personal and stable location edits isolated', () => {
    function BothAddresses() {
      const [personal, setPersonal] = useState<MemberAddressValue>({ city: 'Personal city' });
      const [stable, setStable] = useState<MemberAddressValue>({ city: 'Stable city' });
      return <>
        <MemberAddressFields section="personal" value={personal}
          onChange={(patch) => setPersonal((current) => ({ ...current, ...patch }))} />
        <MemberAddressFields section="stable" value={stable}
          onChange={(patch) => setStable((current) => ({ ...current, ...patch }))} />
      </>;
    }
    render(<BothAddresses />);

    fireEvent.change(screen.getAllByLabelText('City')[0], { target: { value: 'Updated personal city' } });
    expect((screen.getAllByLabelText('City')[0] as HTMLInputElement).value).toBe('Updated personal city');
    expect((screen.getAllByLabelText('City')[1] as HTMLInputElement).value).toBe('Stable city');
  });

  it('cancels personal lookup without cancelling the stable lookup', async () => {
    vi.useFakeTimers();
    const resolvers: Array<(result: { status: 'match'; candidates: typeof completeCandidate[] }) => void> = [];
    vi.mocked(authApi.lookupProviderPostalCode).mockImplementation(() =>
      new Promise((resolve) => { resolvers.push(resolve); }));
    render(<><AddressHarness /><AddressHarness section="stable" /></>);
    const postals = screen.getAllByLabelText('Pincode / Postal code');
    fireEvent.change(postals[0], { target: { value: '11111' } });
    fireEvent.change(postals[1], { target: { value: '22222' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(550); });
    fireEvent.change(screen.getAllByLabelText('City')[0], { target: { value: 'Manual city' } });
    expect(vi.mocked(authApi.lookupProviderPostalCode).mock.calls[0][1]?.aborted).toBe(true);
    expect(vi.mocked(authApi.lookupProviderPostalCode).mock.calls[1][1]?.aborted).toBe(false);
    await act(async () => {
      resolvers.forEach((resolve) => resolve({ status: 'match', candidates: [completeCandidate] }));
    });
    expect((screen.getAllByLabelText('City')[0] as HTMLInputElement).value).toBe('Manual city');
    expect((screen.getAllByLabelText('City')[1] as HTMLInputElement).value).toBe('Austin');
  });

  it('preserves replacement saved values and aborts the previous request', async () => {
    vi.useFakeTimers();
    let resolve!: (result: { status: 'match'; candidates: typeof completeCandidate[] }) => void;
    vi.mocked(authApi.lookupProviderPostalCode).mockImplementation(() =>
      new Promise((res) => { resolve = res; }));
    const onChange = vi.fn();
    const view = render(<MemberAddressFields section="personal" value={{}} onChange={onChange} />);
    await lookup();
    onChange.mockClear();
    view.rerender(<MemberAddressFields section="personal"
      value={{ postal_code: '99999', city: 'Saved correction' }} onChange={onChange} />);
    await act(async () => { resolve({ status: 'match', candidates: [completeCandidate] }); });
    expect(onChange).not.toHaveBeenCalled();
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Saved correction');
    expect(authApi.lookupProviderPostalCode).toHaveBeenCalledTimes(1);
  });
});