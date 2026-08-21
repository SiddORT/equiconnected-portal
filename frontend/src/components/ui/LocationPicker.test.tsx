import { useState } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import {
  LocationPicker,
  type GeographicLocationValue,
} from './LocationPicker';

function ControlledPicker({ initialValue }: { initialValue: GeographicLocationValue }) {
  const [value, setValue] = useState(initialValue);
  return (
    <>
      <LocationPicker value={value} onChange={setValue} idPrefix="test-location" required />
      <output data-testid="location-value">{JSON.stringify(value)}</output>
    </>
  );
}

afterEach(cleanup);

describe('LocationPicker', () => {
  it('initializes existing saved values and filters city choices by the selected state', async () => {
    const user = userEvent.setup();
    render(
      <ControlledPicker
        initialValue={{
          country: 'United States',
          state_province: 'California',
          city: 'Los Angeles',
        }}
      />
    );

    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('United States');
    expect(screen.getByRole('button', { name: 'State / Province' }).textContent).toContain('California');
    expect(screen.getByRole('button', { name: 'City' }).textContent).toContain('Los Angeles');

    await user.click(screen.getByRole('button', { name: 'City' }));
    const search = screen.getByRole('combobox', { name: 'Search city' });
    await user.type(search, 'Acalanes Ridge');
    expect(screen.getByRole('option', { name: 'Acalanes Ridge' })).toBeTruthy();
  });

  it('searches countries and clears dependent selections after a country change', async () => {
    const user = userEvent.setup();
    render(
      <ControlledPicker
        initialValue={{
          country: 'United States',
          state_province: 'California',
          city: 'Los Angeles',
        }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Country' }));
    const search = screen.getByRole('combobox', { name: 'Search country' });
    await user.type(search, 'Canada');
    await user.click(screen.getByRole('option', { name: 'Canada' }));

    expect(screen.getByTestId('location-value').textContent).toBe(
      JSON.stringify({ country: 'Canada', state_province: '', city: '' })
    );
    expect(screen.getByRole('button', { name: 'City' }).hasAttribute('disabled')).toBe(true);
  });

  it('supports a complete country, state, and city selection with the keyboard', async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initialValue={{ country: '', state_province: '', city: '' }} />);

    const countryTrigger = screen.getByRole('button', { name: 'Country' });
    await user.click(countryTrigger);
    await user.type(screen.getByRole('combobox', { name: 'Search country' }), 'Canada');
    await user.keyboard('{ArrowDown}{Enter}');
    await waitFor(() => expect(document.activeElement).toBe(countryTrigger));

    const stateTrigger = screen.getByRole('button', { name: 'State / Province' });
    await user.click(stateTrigger);
    await user.type(screen.getByRole('combobox', { name: 'Search state / province' }), 'Alberta');
    await user.keyboard('{ArrowDown}{Enter}');

    const cityTrigger = screen.getByRole('button', { name: 'City' });
    await user.click(cityTrigger);
    const citySearch = screen.getByRole('combobox', { name: 'Search city' });
    await user.type(citySearch, 'Calgary');
    expect(citySearch.getAttribute('aria-activedescendant')).toContain('-option-0');
    await user.keyboard('{ArrowDown}{Enter}');

    expect(screen.getByTestId('location-value').textContent).toBe(
      JSON.stringify({ country: 'Canada', state_province: 'Alberta', city: 'Calgary' })
    );
    await waitFor(() => expect(document.activeElement).toBe(cityTrigger));
  });

  it('restores focus to the trigger when a search is dismissed', async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initialValue={{ country: '', state_province: '', city: '' }} />);

    const countryTrigger = screen.getByRole('button', { name: 'Country' });
    await user.click(countryTrigger);
    await user.keyboard('{Escape}');

    await waitFor(() => expect(document.activeElement).toBe(countryTrigger));
  });
});
