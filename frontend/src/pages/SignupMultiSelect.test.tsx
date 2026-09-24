import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { SignupMultiSelect } from './SignupMultiSelect';

afterEach(() => cleanup());

describe.each(['dark', 'light'] as const)('%s multi-select bulk action', (tone) => {
  it('works with keyboard, ignores empty matches, and preserves unloaded selections', async () => {
    const onChange = vi.fn();
    function Picker() {
      const [ids, setIds] = useState(['unloaded', 'outside']);
      return <SignupMultiSelect
        tone={tone} label="Specializations"
        options={[
          { id: 'outside', name: 'Emergency care' },
          { id: 'first', name: 'Dental care' },
          { id: 'second', name: 'Dental surgery' },
        ]}
        selectedIds={ids}
        onChange={(next) => { setIds(next); onChange(next); }}
      />;
    }
    const user = userEvent.setup();
    render(<Picker />);
    await user.click(screen.getByRole('button', { name: 'Specializations' }));
    const search = screen.getByRole('searchbox', { name: 'Search specializations' });
    await user.type(search, 'dental');
    const select = screen.getByRole('button', { name: 'Select all' });
    select.focus();
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenLastCalledWith(['unloaded', 'outside', 'first', 'second']);
    expect(screen.getByRole('button', { name: 'Specializations' }).textContent).toContain('4 selected');
    const clear = screen.getByRole('button', { name: 'Clear all' });
    clear.focus();
    await user.keyboard(' ');
    expect(onChange).toHaveBeenLastCalledWith(['unloaded', 'outside']);
    await user.clear(search);
    await user.type(search, 'no results');
    expect(screen.getByText('No matching options')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Select all' }).hasAttribute('disabled')).toBe(true);
  });

  it('disables the picker while loading or without available options', () => {
    const { rerender } = render(<SignupMultiSelect tone={tone} label="Languages" options={[{ id: 'en', name: 'English' }]} selectedIds={[]} onChange={vi.fn()} loading />);
    expect(screen.getByRole('button', { name: 'Languages' }).hasAttribute('disabled')).toBe(true);
    rerender(<SignupMultiSelect tone={tone} label="Languages" options={[]} selectedIds={[]} onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Languages' }).hasAttribute('disabled')).toBe(true);
  });
});