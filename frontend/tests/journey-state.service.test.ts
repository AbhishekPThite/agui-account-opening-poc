import test from 'node:test';
import assert from 'node:assert/strict';
import { JourneyStateService } from '../src/app/journey-state.service';

test('starts with an empty journey state', () => {
  const state = new JourneyStateService();
  assert.deepEqual(state.events(), []);
  assert.deepEqual(state.assistantText(), []);
  assert.equal(state.uiState(), null);
  assert.equal(state.busy(), false);
  assert.equal(state.error(), '');
  assert.equal(state.pendingInterruptId(), null);
});

test('records events and applies a valid UI snapshot', () => {
  const state = new JourneyStateService();
  const event = { type: 'STATE_SNAPSHOT', snapshot: {} };
  state.recordEvent(event);
  state.applySnapshot({
    ui: { widgetId: 'ACCOUNT_SETUP_FORM', mode: 'FORM', title: 'Account setup' }
  });
  assert.deepEqual(state.events(), [event]);
  assert.equal(state.uiState()?.title, 'Account setup');
});

test('ignores malformed or missing UI snapshots', () => {
  const state = new JourneyStateService();
  state.applySnapshot(undefined);
  state.applySnapshot({ ui: { widgetId: 'ONLY_ID' } });
  assert.equal(state.uiState(), null);
});

test('accumulates streamed assistant text in the current message', () => {
  const state = new JourneyStateService();
  state.appendAssistantMessage();
  state.appendAssistantText('Hello ');
  state.appendAssistantText('world');
  state.appendAssistantMessage();
  state.appendAssistantText('Next');
  assert.deepEqual(state.assistantText(), ['Hello world', 'Next']);
});

test('calculates completion percentage and safely handles an empty journey', () => {
  const state = new JourneyStateService();
  assert.equal(state.completionPercent(), 0);
  state.applySnapshot({
    ui: {
      widgetId: 'APPLICATION_DASHBOARD',
      mode: 'SUMMARY',
      title: 'Progress',
      journeyStatus: { completedCount: 2, totalCount: 5 }
    }
  });
  assert.equal(state.completionPercent(), 40);
});

test('reset clears state, errors, interrupts and busy status', () => {
  const state = new JourneyStateService();
  state.recordEvent({ type: 'RUN_ERROR' });
  state.appendAssistantText('partial');
  state.setInterrupt('interrupt-1');
  state.setError('failed');
  state.busy.set(true);
  state.reset();
  assert.deepEqual(state.events(), []);
  assert.deepEqual(state.assistantText(), []);
  assert.equal(state.pendingInterruptId(), null);
  assert.equal(state.error(), '');
  assert.equal(state.busy(), false);
});
