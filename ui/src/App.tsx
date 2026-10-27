import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router';
import { NoLoginBanner } from '@/components/organisms/NoLoginBanner';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { AppShell } from '@/components/templates/AppShell';
import { useAuthRedirects } from '@/hooks/useAuthRedirects';
import { useServerInfo } from '@/hooks/useServer';
import { ADD_HOME_PATH, SETUP_PATH, SIGN_IN_PATH } from '@/lib/links';
import { DevicePage } from '@/pages/DevicePage';
import { HomePage } from '@/pages/HomePage';
import { HomesPage } from '@/pages/HomesPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { SetupPage } from '@/pages/SetupPage';
import { SignInPage } from '@/pages/SignInPage';

// The wizard (and its QR encoder) loads only when someone adds a device.
const AddDevicePage = lazy(() => import('@/pages/AddDevicePage'));
// Folded to null in production builds, so the gallery chunk is never emitted.
const ComponentGallery = import.meta.env.DEV ? lazy(() => import('@/dev/ComponentGallery')) : null;

/**
 * Boot routing (v3): `/server-info` decides. Setup required → every URL shows setup; ready → setup
 * redirects home; a 401 anywhere → sign-in. In auth mode `none` the banner tops every app page.
 */
function BootGate() {
  const info = useServerInfo();
  const { pathname } = useLocation();
  useAuthRedirects();

  if (!info.data) {
    // While boot loads: the empty app frame, no spinner text.
    return <AppShell>{info.isError && <QueryBoundary query={info} what="OpenFLO">{() => null}</QueryBoundary>}</AppShell>;
  }
  const settingUp = info.data.setup_state === 'setup_required';
  // Leaving /setup means setup just finished: land on Homes with Add home open (v3 §12 done).
  if (settingUp !== (pathname === SETUP_PATH)) return <Navigate to={settingUp ? SETUP_PATH : ADD_HOME_PATH} replace />;
  const banner = info.data.auth.mode === 'none' && !settingUp && pathname !== SIGN_IN_PATH;
  return (
    <>
      {banner && <NoLoginBanner />}
      <Outlet />
    </>
  );
}

export function App() {
  return (
    <Routes>
      {ComponentGallery && (
        <Route
          path="/__components"
          element={
            <Suspense fallback={null}>
              <ComponentGallery />
            </Suspense>
          }
        />
      )}
      <Route element={<BootGate />}>
        <Route path={SETUP_PATH} element={<SetupPage />} />
        <Route path={SIGN_IN_PATH} element={<SignInPage />} />
        <Route path="/" element={<HomesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/homes/:homeId" element={<HomePage />} />
        <Route
          path="/homes/:homeId/add/:sessionId?"
          element={
            <Suspense fallback={null}>
              <AddDevicePage />
            </Suspense>
          }
        />
        <Route path="/devices/:deviceId" element={<DevicePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
