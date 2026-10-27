import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Notice } from './Notice';

describe('Notice', () => {
  it('announces errors with role="alert"', () => {
    render(
      <Notice tone="bad" role="alert">
        Couldn’t reach the server.
      </Notice>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Couldn’t reach the server.');
  });

  it('is static text without a role', () => {
    render(<Notice tone="warn">This liquid can dose 28–816 mL.</Notice>);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('This liquid can dose 28–816 mL.')).toHaveClass('bg-warn-soft');
  });
});
