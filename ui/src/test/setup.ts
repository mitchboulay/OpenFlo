import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// Page tests wait on real async renders (msw, TanStack Query). The 1 s default flakes on a loaded machine or a
// slow CI runner; 5 s only matters when something is genuinely slow, and a real failure still fails.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());
