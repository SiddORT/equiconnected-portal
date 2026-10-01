import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { SignupMultiSelect } from './SignupMultiSelect';

afterEach(() => cleanup());

describe.each(['dark', 'light'] as const)('%s multi-select bulk action', (tone) => {
  it('searches by code, toggles individual selections, removes chips and dismisses without losing selections', async () => {
    function Picker() {
      const [ids, setIds] = useState(['en']);
      return <SignupMultiSelect tone={tone} label="Languages"
        options={[{ id: 'en', name: 'English', code: 'en' }, { id: 'fr', name: 'French', code: 'fr' }]}
        selectedIds={ids} onChange={setIds} />;
    }
    const user = userEvent.setup();
    render(<Picker />);
    const trigger = screen.getByRole('button', { name: 'Languages' });
    await user.click(trigger);
    const search = screen.getByRole('searchbox', { name: 'Search languages' });
    expect(document.activeElement).toBe(search);
    await user.type(search, ' FR ');
    expect(screen.queryByRole('option', { name: 'English (en)' })).toBeNull();
    await user.click(screen.getByRole('option', { name: 'French (fr)' }));
    expect(screen.getByRole('option', { name: 'French (fr)' }).getAttribute('aria-selected')).toBe('true');
    await user.click(screen.getByRole('option', { name: 'French (fr)' }));
    expect(screen.queryByRole('button', { name: 'Remove French' })).toBeNull();
    await user.click(screen.getByRole('option', { name: 'French (fr)' }));
    await user.click(screen.getByRole('button', { name: 'Remove English' }));
    await user.click(search);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).toBeNull();
    await user.click(trigger);
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('');
    expect(screen.getByRole('option', { name: 'French (fr)' }).getAttribute('aria-selected')).toBe('true');
    await user.click(document.body);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByRole('button', { name: 'Remove French' })).toBeTruthy();
  });

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