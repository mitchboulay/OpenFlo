# OpenFLO UI

React 18 + TypeScript (strict) SPA, built with Vite and Tailwind CSS v4. The
backend serves the build (`ui/dist`) at `/` with history fallback.

## Develop

```bash
# Terminal 1: backend on :8099
cd backend
OPENFLO_BACKEND_DB="$PWD/openflo-backend.db" \
  python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8099

# Terminal 2: UI with hot reload on :5173
cd ui
npm ci
npm run dev
```

`npm run dev` proxies `/api` and `/healthz` to `http://127.0.0.1:8099`.

No backend handy? `VITE_MSW=1 npm run dev` serves a fake `/api/v1` from a
service worker (`src/dev/fakeProvisioningBackend.ts`, the same fake the wizard
tests use). Add `?mock=lan`, `?mock=lan-fails` or `?mock=unverified` to the
first URL to pick a scenario, and call `window.__openfloFake.advance()` or
`.expire()` in the console to play the device. Production builds contain none of it.

Open <http://localhost:5173/__components> for the component gallery: every
`*.examples.tsx` file, rendered live. It exists only in dev; production builds
leave it out.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm test -- --run` | Vitest + Testing Library + msw, once |
| `npm run build` | `gen:api`, API drift check, type check, production build to `dist/` |
| `npm run gen:api` | Regenerates `src/api/schema.d.ts` from `../backend/openapi.json` |
| `npm run typecheck` | `tsc --noEmit` |

## API contract

The TypeScript types come from the backend's OpenAPI document:

```bash
cd backend && python -m app.export_openapi   # writes backend/openapi.json
cd ui && npm run gen:api                     # writes src/api/schema.d.ts
```

Commit both files. A backend test fails when `openapi.json` is stale, and
`npm run build` fails when `schema.d.ts` differs from the committed copy.

## Structure

```
src/
├── api/          client.ts (typed fetch, ApiError), endpoints.ts (one call per endpoint), types.ts,
│                 queryKeys.ts, queryClient.ts, schema.d.ts (generated)
├── components/
│   ├── atoms/        Badge, Button, Icon, IconButton, Input, LevelBars, Notice, QrCode, Select, Sparkline, StatusDot,
│   │                 Switch
│   ├── molecules/    BottleGauge, CheckinOption, CheckList, ChoiceChips, ConfirmButton, CopyField, DayPicker,
│   │                 DispenseTracker, Field, ListRow, Menu, PasswordInput, PendingBadge, PendingRow,
│   │                 SectionCard, SectionNav, StatusPill, StepDots, Stepper, Tabs
│   ├── organisms/    HomeList, DeviceList, DeviceHeader, DosingCard, ScheduleEditor, WifiCard, SetupWizard,
│   │                 SignInForm, the Settings cards, NoLoginBanner, … and their sheets
│   └── templates/    AppShell, DeviceLayout, Sheet, WizardShell
├── pages/        HomesPage (/), HomePage (/homes/:id), DevicePage (/devices/:id),
│                 AddDevicePage (/homes/:id/add/:sessionId?, lazy), SetupPage (/setup),
│                 SignInPage (/sign-in?next=), SettingsPage (/settings); templates + organisms only
├── hooks/        useHomes, useDevice (10 s polling), useDosing, useSchedule, useUnits, useServer (server info,
│                 setup, address check), useAuth (sign-in, tokens), useAuthRedirects, useAction,
│                 useDebouncedCommit, useFocusTrap
├── lib/          time, units (the one volume formatter), events (firmware names), deviceStatus, schedule, errors,
│                 addressCheck (check titles and fixes), links
├── styles/       tokens.css (the only file with raw colors), index.css (Tailwind theme)
├── dev/          Component gallery (dev only)
└── types/
```

Rules (from `docs/design/critique-v2.md`):

- Each component lives at exactly one atomic level. Every atom and molecule ships with a test and an `*.examples.tsx`.
- Colors come only from tokens (`bg-surface`, `text-dim`, `bg-accent`, ...). Tailwind's default palette is disabled, and a test fails on raw hex, `rgb()` or `hsl()` in components.
- Mobile first: base styles target 360 px; breakpoints `sm` (640 px) and `lg` (1024 px). Touch targets are at least 44×44 px.
- Theme follows the OS. `<html data-theme="light|dark">` overrides it.
- The UI never computes doses or guidance and never holds a token; the backend owns both.

## Verifying phone widths

Desktop Chrome, including `--headless`, won't lay out narrower than 500 px: `--window-size=360,…` still gives `innerWidth = 500`, so its "360 px" screenshots are wrong. To get a true 360 px viewport, load the page in a 360 px iframe inside a 500 px window:

```bash
printf '<!doctype html><body style="margin:0"><iframe src="http://localhost:8099/" width="360" height="780" style="border:0"></iframe>' > /tmp/f360.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars \
  --window-size=500,780 --virtual-time-budget=3000 --screenshot=/tmp/s.png file:///tmp/f360.html
sips -c 780 360 --cropOffset 0 0 /tmp/s.png --out docs/screenshots/<task>-<page>-360.png
```

Use the address the server actually binds (Vite's dev server answers on `localhost`, not `127.0.0.1`).
