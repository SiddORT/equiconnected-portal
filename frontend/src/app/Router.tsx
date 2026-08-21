/**
 * Application router.
 * Adding new module routes (hospital, visitor) happens here — deliberately.
 */
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthGuard } from '@/features/admin/AuthGuard';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { PublicPage } from '@/pages/PublicPage';
import { LoginPage } from '@/pages/admin/LoginPage';
import { DashboardPage } from '@/pages/admin/DashboardPage';
import { SpecializationsPage } from '@/pages/admin/SpecializationsPage';
import { ProvidersPage } from '@/pages/admin/ProvidersPage';
import { ProviderNewPage } from '@/pages/admin/ProviderNewPage';
import { ProviderDetailPage } from '@/pages/admin/ProviderDetailPage';
import { ProviderEditPage } from '@/pages/admin/ProviderEditPage';
import { LegacyDoctorRedirect } from '@/pages/admin/LegacyDoctorRedirect';
import { InvitationsPage } from '@/pages/admin/InvitationsPage';
import { ActivityLogsPage } from '@/pages/admin/ActivityLogsPage';
import { InvitationPage } from '@/pages/InvitationPage';
import { SubmissionSuccessPage } from '@/pages/SubmissionSuccessPage';
import { SignupPage } from '@/pages/SignupPage';
import { VerifyEmailPage } from '@/pages/VerifyEmailPage';
import { LegalPage } from '@/pages/LegalPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Public ──────────────────────────────────────────────── */}
        <Route path="/" element={<PublicPage />} />
        <Route path="/provider/invite/success" element={<SubmissionSuccessPage />} />
        <Route path="/provider/invite/:token" element={<InvitationPage />} />
        {/* Emailed links use /provider/invitations/{token} — same page. */}
        <Route path="/provider/invitations/:token" element={<InvitationPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/terms-of-service" element={<LegalPage kind="terms" />} />
        <Route path="/privacy-policy" element={<LegalPage kind="privacy" />} />

        {/* ── Admin auth ──────────────────────────────────────────── */}
        <Route path="/admin/login" element={<LoginPage />} />

        {/* ── Admin protected ─────────────────────────────────────── */}
        <Route element={<AuthGuard requiredRole="admin" />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
            <Route path="/admin/dashboard" element={<DashboardPage />} />
            <Route path="/admin/specializations" element={<SpecializationsPage />} />
            <Route path="/admin/providers" element={<ProvidersPage />} />
            <Route path="/admin/providers/new" element={<ProviderNewPage />} />
            <Route path="/admin/providers/:id" element={<ProviderDetailPage />} />
            <Route path="/admin/providers/:id/edit" element={<ProviderEditPage />} />
            {/* Legacy doctor routes → unified Provider Management */}
            <Route
              path="/admin/doctors"
              element={<Navigate to="/admin/providers?provider_type=DOCTOR" replace />}
            />
            <Route
              path="/admin/doctors/new"
              element={<Navigate to="/admin/providers/new" replace />}
            />
            <Route path="/admin/doctors/:id" element={<LegacyDoctorRedirect />} />
            <Route path="/admin/doctors/:id/edit" element={<LegacyDoctorRedirect edit />} />
            <Route path="/admin/invitations" element={<InvitationsPage />} />
            <Route path="/admin/activity-logs" element={<ActivityLogsPage />} />
          </Route>
        </Route>

        {/* ── Fallback ─────────────────────────────────────────────── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
