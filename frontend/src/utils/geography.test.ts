import { describe, expect, it } from 'vitest';
import {
  getCityOptions,
  getCountryOptions,
  getStateOptions,
} from './geography';

describe('geography data dependency', () => {
  it('loads country, state, and city options from country-state-city', () => {
    const countries = getCountryOptions();
    const states = getStateOptions('Canada');
    const cities = getCityOptions('Canada', 'Alberta');

    expect(countries).toContainEqual({ value: 'Canada', label: 'Canada' });
    expect(states).toContainEqual({ value: 'Alberta', label: 'Alberta' });
    expect(cities).toContainEqual({ value: 'Calgary', label: 'Calgary' });
  });
});