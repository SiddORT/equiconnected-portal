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

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Public ──────────────────────────────────────────────── */}
        <Route path="/" element={<PublicPage />} />

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
          </Route>
        </Route>

        {/* ── Fallback ─────────────────────────────────────────────── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
