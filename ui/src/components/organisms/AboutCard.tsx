import { ListRow } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';

export interface AboutCardProps {
  version: string;
}

/** Settings → About. */
export function AboutCard({ version }: AboutCardProps) {
  return (
    <SectionCard title="About" icon="info">
      <ul className="m-0 list-none p-0">
        <ListRow title="Version" value={version} mono />
      </ul>
    </SectionCard>
  );
}
