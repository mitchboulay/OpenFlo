import { Icon } from '@/components/atoms/Icon';
import { SIGN_IN_DOCS_URL } from '@/lib/links';

/**
 * Auth mode `none` (FR-15): one warn line above every app page. Not dismissible, since it stays
 * true; on a phone the middle clause truncates first, never the link. `status`, so it isn't
 * re-announced on every navigation.
 */
export function NoLoginBanner() {
  return (
    <div role="status" className="bg-warn-soft text-sm text-fg">
      <div className="mx-auto flex min-h-11 max-w-wide items-center gap-1.5 px-4 whitespace-nowrap">
        <Icon name="warning" size={16} className="flex-none text-warn" />
        <span className="flex-none font-semibold">No login</span>
        <span aria-hidden="true" className="flex-none text-dim">·</span>
        <span className="min-w-0 truncate">anyone on your network can control your devices</span>
        <span aria-hidden="true" className="flex-none text-dim">·</span>
        <a href={SIGN_IN_DOCS_URL} target="_blank" rel="noreferrer" className="flex-none font-semibold text-accent-text">
          Turn on sign-in
        </a>
      </div>
    </div>
  );
}
