import { describe, expect, it } from 'vitest';
import { describeEventBatch, dispenseKind, eventName } from './events';

describe('firmware event names', () => {
  it('names known SE and EE codes and falls back for the rest', () => {
    expect(eventName(0, 8)).toBe('Dispensed on request');
    expect(eventName(0, 3)).toBe('Dispensed a double dose');
    expect(eventName(1, 5)).toBe('New bottle put in');
    expect(eventName(1, 6)).toBe('Bottle removed');
    expect(eventName(0, 13)).toBe('Device event');
  });

  it('expands a send-events batch into rows at device time, with codes', () => {
    const rows = describeEventBatch({
      id: 9,
      kind: 'send-events',
      received_at: '2026-10-26T21:00:00Z',
      payload: { data: [{ status: 1, code: 6, timestamp: 1_761_512_400 }, { status: 0, code: 13 }, { bogus: true }] },
    });
    expect(rows).toEqual([
      { key: '9-0', name: 'Bottle removed', code: 'EE 6', at: new Date(1_761_512_400_000).toISOString() },
      { key: '9-1', name: 'Device event', code: 'SE 13', at: '2026-10-26T21:00:00Z' },
    ]);
  });

  it('names request batches and empty event batches', () => {
    expect(describeEventBatch({ id: 1, kind: 'get-fw', received_at: 't', payload: {} })[0]?.name).toBe('Checked for a firmware update');
    expect(describeEventBatch({ id: 2, kind: 'send-events', received_at: 't', payload: {} })[0]?.name).toBe('Reported events');
    expect(describeEventBatch({ id: 3, kind: 'mystery', received_at: 't', payload: null })[0]?.name).toBe('mystery');
  });

  it('labels dispense history kinds', () => {
    expect(dispenseKind(8, 1)).toBe('On request');
    expect(dispenseKind(3, 2)).toBe('Double dose');
    expect(dispenseKind(1, 1)).toBe('Dose');
  });
});
