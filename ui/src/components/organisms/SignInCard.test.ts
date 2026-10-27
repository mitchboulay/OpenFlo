import { describe, expect, it } from 'vitest';
import { actorLabel } from './SignInCard';

describe('actorLabel', () => {
  it.each([
    ['user:admin', 'admin'],
    ['oidc:alice@example.com', 'alice@example.com'],
    ['proxy:bob', 'bob'],
    ['operator:local', 'Local operator'],
    ['bootstrap', 'bootstrap'],
    ['setup:wizard', 'setup:wizard'],
  ])('%s → %s', (actor, label) => {
    expect(actorLabel(actor)).toBe(label);
  });
});
