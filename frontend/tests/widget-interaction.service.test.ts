import test from 'node:test';
import assert from 'node:assert/strict';
import { WidgetInteractionService } from '../src/app/widget-interaction.service';
import { AgentUI } from '../src/app/models/agent-ui.model';

const service = new WidgetInteractionService();

test('maps beneficiary skip to the beneficiary skip form command', () => {
  const command = service.toCommand({ __beneficiaryAction: 'SKIP' }, null);
  assert.deepEqual(command, {
    type: 'message',
    text: 'POC_FORM_SUBMISSION:{"formId":"BENEFICIARY_SKIP"}'
  });
});

test('maps profile confirm and edit actions to their respective form commands', () => {
  const confirm = service.toCommand({ __profileAction: 'CONFIRM' }, null);
  const edit = service.toCommand({ __profileAction: 'EDIT' }, null);
  assert.deepEqual(confirm, {
    type: 'message',
    text: 'POC_FORM_SUBMISSION:{"formId":"PROFILE_CONFIRMATION"}'
  });
  assert.deepEqual(edit, {
    type: 'message',
    text: 'POC_FORM_SUBMISSION:{"formId":"PROFILE_CAPTURE_REQUEST"}'
  });
});

test('maps approval and rejection to resume commands', () => {
  assert.deepEqual(service.toCommand({ __approvalAction: 'APPROVE' }, null), {
    type: 'resume',
    payload: { action: 'APPROVE', approved: true }
  });
  assert.deepEqual(service.toCommand({ __approvalAction: 'REJECT' }, null), {
    type: 'resume',
    payload: { action: 'REJECT', approved: false }
  });
});

test('maps supported widget IDs to their backend form IDs', () => {
  const cases: Array<[string, string]> = [
    ['ACCOUNT_SETUP_FORM', 'ACCOUNT_SETUP'],
    ['JOINT_OWNER_FORM', 'JOINT_OWNER_DETAILS'],
    ['PROFILE_DATA_CAPTURE', 'PROFILE_DATA_CAPTURE'],
    ['BENEFICIARY_CAPTURE', 'BENEFICIARY_CAPTURE'],
    ['RISK_ASSESSMENT_FORM', 'RISK_ASSESSMENT'],
    ['PRODUCT_FEATURES_FORM', 'PRODUCT_FEATURES']
  ];
  for (const [widgetId, formId] of cases) {
    const ui = { widgetId, mode: 'FORM', title: 'Form' } as AgentUI;
    const command = service.toCommand({ firstName: 'Alex' }, ui);
    assert.deepEqual(command, {
      type: 'message',
      text: `POC_FORM_SUBMISSION:{"firstName":"Alex","formId":"${formId}"}`
    });
  }
});

test('falls back to a readable message for an unknown widget', () => {
  const command = service.toCommand({ firstName: 'Alex', riskLevel: 'LOW' }, null);
  assert.deepEqual(command, {
    type: 'message',
    text: 'Here are the requested account-opening details: first name: Alex, risk level: LOW'
  });
});
