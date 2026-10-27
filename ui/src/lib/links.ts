/** "How to turn on sign-in" (docs/deploy.md § Sign-in), shown by the setup wizard, Settings and the banner. */
export const SIGN_IN_DOCS_URL = 'https://github.com/mitchboulay/OpenFlo/blob/main/docs/deploy.md#sign-in';

export const SETUP_PATH = '/setup';
export const SIGN_IN_PATH = '/sign-in';
/** Homes with the Add home sheet open (read by HomeList), where setup ends. */
export const ADD_HOME_PATH = '/?add=home';

/** `?next=` for the sign-in page, back to `path` afterwards. */
export function signInPath(path: string): string {
  return `${SIGN_IN_PATH}?next=${encodeURIComponent(path)}`;
}

/** A same-app path to return to after sign-in; anything else (another origin, `//host`) becomes `/`. */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/';
  return next.startsWith(SIGN_IN_PATH) ? '/' : next;
}
