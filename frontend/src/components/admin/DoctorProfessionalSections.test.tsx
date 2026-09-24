import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DoctorProfessionalSections } from './DoctorProfessionalSections';
import { getDoctor, updateDoctorQualification } from '@/api/doctors';
import type { DoctorResponse } from '@/types/doctor';

vi.mock('@/api/doctors', () => ({
  getDoctor: vi.fn(),
  addDoctorQualification: vi.fn(),
  updateDoctorQualification: vi.fn(),
  deleteDoctorQualification: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('doctor detail qualifications', () => {
  it('shows qualification details and actions without loading or showing affiliations', async () => {
    const qualification = {
      id: 'q1', provider_id: 'doctor-1', title: 'DVM',
      institution: 'Western College', year_obtained: 2018, description: 'Equine medicine',
      display_order: 0, created_at: '', updated_at: '',
    };
    vi.mocked(getDoctor).mockResolvedValue({
      qualifications: [qualification],
      organizations: [{ id: 'affiliation-1', organization: { id: 'clinic-1', name: 'Hidden clinic', provider_type: 'CLINIC' } }],
    } as DoctorResponse);
    render(<DoctorProfessionalSections providerId="doctor-1" />);
    expect(await screen.findByRole('heading', { name: 'Qualifications' })).toBeTruthy();
    expect(screen.getByText('DVM')).toBeTruthy();
    expect(screen.getByText(/Western College · 2018 — Equine medicine/)).toBeTruthy();
    expect(screen.queryByText('Affiliations')).toBeNull();
    expect(screen.queryByText('Hidden clinic')).toBeNull();
    expect(screen.queryByRole('button', { name: /Add affiliation/i })).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Edit/ }));
    expect((screen.getByLabelText('Institution') as HTMLInputElement).value).toBe('Western College');
    expect((screen.getByLabelText('Year obtained') as HTMLInputElement).value).toBe('2018');
    vi.mocked(updateDoctorQualification).mockResolvedValue({ ...qualification, institution: 'New College' });
    await user.clear(screen.getByLabelText('Institution'));
    await user.type(screen.getByLabelText('Institution'), 'New College');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateDoctorQualification).toHaveBeenCalledWith(
      'doctor-1', 'q1', expect.objectContaining({ institution: 'New College', year_obtained: 2018 })
    ));
    expect(screen.getByRole('button', { name: /Add qualification/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Remove/i })).toBeTruthy();
  });
});