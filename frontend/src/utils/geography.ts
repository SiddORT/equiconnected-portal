import { City, Country, State } from 'country-state-city';

export interface GeographicOption {
  value: string;
  label: string;
}

function hasSameText(left: string, right: string) {
  return left.trim().localeCompare(right.trim(), undefined, { sensitivity: 'accent' }) === 0;
}

export function getCountryOptions(): GeographicOption[] {
  return Country.getAllCountries()
    .map((country) => ({ value: country.name, label: country.name }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

function findCountry(countryName: string) {
  return Country.getAllCountries().find(
    (country) =>
      hasSameText(country.name, countryName) ||
      country.isoCode.localeCompare(countryName.trim(), undefined, { sensitivity: 'accent' }) === 0
  );
}

function findState(countryName: string, stateName: string) {
  const country = findCountry(countryName);
  if (!country || !stateName.trim()) return undefined;

  return State.getStatesOfCountry(country.isoCode).find(
    (state) =>
      hasSameText(state.name, stateName) ||
      state.isoCode.localeCompare(stateName.trim(), undefined, { sensitivity: 'accent' }) === 0
  );
}

export function getStateOptions(countryName: string): GeographicOption[] {
  const country = findCountry(countryName);
  if (!country) return [];

  return State.getStatesOfCountry(country.isoCode)
    .map((state) => ({ value: state.name, label: state.name }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

export function getCityOptions(countryName: string, stateName: string): GeographicOption[] {
  const country = findCountry(countryName);
  if (!country) return [];

  const state = findState(countryName, stateName);
  const cities = (state
    ? City.getCitiesOfState(country.isoCode, state.isoCode)
    : City.getCitiesOfCountry(country.isoCode)) ?? [];

  return Array.from(new Set(cities.map((city) => city.name)))
    .sort((left, right) => left.localeCompare(right))
    .map((city) => ({ value: city, label: city }));
}
