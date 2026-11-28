import test from 'node:test';
import assert from 'node:assert/strict';
import { Observable, of, Subject } from 'rxjs';
import { ConversationService } from '../src/app/conversation.service';
import { AgUiEventProcessor } from '../src/app/ag-ui-event-processor.service';
import { JourneyStateService } from '../src/app/journey-state.service';
import { AguiClientService, RunAgentInput } from '../src/app/agui-client.service';

function setup(runImpl: (input: RunAgentInput) => Observable<any> = () => of()) {
  const inputs: RunAgentInput[] = [];
  const client = {
    run: (input: RunAgentInput) => {
      inputs.push(input);
      return runImpl(input);
    }
  } as unknown as AguiClientService;
  const journey = new JourneyStateService();
  const processor = new AgUiEventProcessor(journey);
  const conversation = new ConversationService(client, processor, journey);
  return { conversation, journey, inputs };
}

test('starts a new thread and sends the initial prompt', () => {
  const { conversation, inputs } = setup();
  conversation.start('Open an account');
  assert.equal(inputs.length, 1);
  assert.equal(inputs[0].messages[0].content, 'Open an account');
  assert.equal(inputs[0].messages[0].role, 'user');
  assert.ok(inputs[0].threadId);
  assert.ok(inputs[0].runId);
});

test('uses the same thread for follow-up messages', () => {
  const { conversation, inputs } = setup();
  conversation.start('Start');
  conversation.sendMessage('Follow up');
  assert.equal(inputs.length, 2);
  assert.equal(inputs[0].threadId, inputs[1].threadId);
  assert.equal(inputs[1].messages[0].content, 'Follow up');
});

test('creates a new thread when starting a new journey', () => {
  const { conversation, inputs } = setup();
  conversation.start('First journey');
  conversation.start('Second journey');
  assert.equal(inputs.length, 2);
  assert.notEqual(inputs[0].threadId, inputs[1].threadId);
});

test('resumes a pending interrupt with the supplied payload', () => {
  const { conversation, journey, inputs } = setup();
  journey.setInterrupt('interrupt-7');
  conversation.resume('interrupt-7', { action: 'APPROVE', approved: true });
  assert.deepEqual(inputs[0].messages, []);
  assert.deepEqual(inputs[0].resume, [{
    interruptId: 'interrupt-7',
    status: 'resolved',
    payload: { action: 'APPROVE', approved: true }
  }]);
});

test('ignores empty messages and prevents overlapping requests', () => {
  const pending = new Subject<any>();
  const { conversation, inputs } = setup(() => pending);
  conversation.sendMessage('   ');
  assert.equal(inputs.length, 0);
  conversation.sendMessage('First');
  conversation.sendMessage('Second');
  assert.equal(inputs.length, 1);
  pending.complete();
  conversation.sendMessage('Third');
  assert.equal(inputs.length, 2);
});
