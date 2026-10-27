export interface SectionNavProps {
  /** Accessible name, e.g. "Device sections". */
  label: string;
  /** In-page targets: `{ id: 'dosing', label: 'Dosing' }` links to `#dosing`. */
  sections: readonly { id: string; label: string }[];
}

/** Jump links to the page's sections (native anchors; targets carry `scroll-margin-top`). */
export function SectionNav({ label, sections }: SectionNavProps) {
  return (
    <nav aria-label={label}>
      <ul className="m-0 flex list-none gap-1.5 overflow-x-auto p-0.5 [scrollbar-width:none]">
        {sections.map((section) => (
          <li key={section.id} className="flex-none">
            <a
              href={`#${section.id}`}
              className="flex min-h-11 items-center rounded-full border border-border bg-surface px-4 text-sm font-medium whitespace-nowrap text-dim no-underline hover:border-border2 hover:text-fg"
            >
              {section.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
