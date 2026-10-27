import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SectionNav } from './SectionNav';

describe('SectionNav', () => {
  it('links each section by anchor inside a named nav', () => {
    render(<SectionNav label="Device sections" sections={[{ id: 'dosing', label: 'Dosing' }, { id: 'device', label: 'Device' }]} />);
    expect(screen.getByRole('navigation', { name: 'Device sections' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dosing' })).toHaveAttribute('href', '#dosing');
    expect(screen.getByRole('link', { name: 'Device' })).toHaveAttribute('href', '#device');
  });
});
