import test from 'node:test';
import assert from 'node:assert/strict';
import { AgUiEventProcessor } from '../src/app/ag-ui-event-processor.service';
import { JourneyStateService } from '../src/app/journey-state.service';

test('records events and applies state snapshots', () => {
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  processor.process({
    type: 'STATE_SNAPSHOT',
    snapshot: { ui: { widgetId: 'APPLICATION_DASHBOARD', mode: 'SUMMARY', title: 'Dashboard' } }
  });
  assert.equal(journey.events().length, 1);
  assert.equal(journey.uiState()?.title, 'Dashboard');
});

test('accumulates streamed assistant text', () => {
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  processor.process({ type: 'TEXT_MESSAGE_START' });
  processor.process({ type: 'TEXT_MESSAGE_CONTENT', delta: 'Account ' });
  processor.process({ type: 'TEXT_MESSAGE_CONTENT', delta: 'opened' });
  assert.deepEqual(journey.assistantText(), ['Account opened']);
});

test('captures the first interrupt ID when a run pauses', () => {
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  processor.process({
    type: 'RUN_FINISHED',
    outcome: { type: 'interrupt', interrupts: [{ id: 'interrupt-123' }] }
  });
  assert.equal(journey.pendingInterruptId(), 'interrupt-123');
});

test('reports an interrupt without an ID and clears interrupts on normal completion', () => {
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  processor.process({ type: 'RUN_FINISHED', outcome: { type: 'interrupt', interrupts: [] } });
  assert.equal(journey.error(), 'The agent paused, but no interrupt ID was returned.');
  journey.setInterrupt('old-interrupt');
  processor.process({ type: 'RUN_FINISHED', outcome: { type: 'success' } });
  assert.equal(journey.pendingInterruptId(), null);
});

test('maps RUN_ERROR to the journey error state', () => {
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  processor.process({ type: 'RUN_ERROR', message: 'Model unavailable' });
  assert.equal(journey.error(), 'Model unavailable');
});
