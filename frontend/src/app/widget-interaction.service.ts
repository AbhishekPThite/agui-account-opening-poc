import { Injectable } from '@angular/core';
import { AgentUI } from './models/agent-ui.model';

export type WidgetCommand =
  | { type: 'message'; text: string }
  | { type: 'resume'; payload: { action: 'APPROVE' | 'REJECT'; approved: boolean } };

@Injectable({ providedIn: 'root' })
export class WidgetInteractionService {
  toCommand(payload: Record<string, unknown>, ui: AgentUI | null): WidgetCommand {
    if (payload['__beneficiaryAction'] === 'SKIP') {
      return this.formSubmission({ formId: 'BENEFICIARY_SKIP' });
    }
    if (payload['__profileAction'] === 'CONFIRM') {
      return this.formSubmission({ formId: 'PROFILE_CONFIRMATION' });
    }
    if (payload['__profileAction'] === 'EDIT') {
      return this.formSubmission({ formId: 'PROFILE_CAPTURE_REQUEST' });
    }

    const approval = payload['__approvalAction'];
    if (approval === 'APPROVE' || approval === 'REJECT') {
      return {
        type: 'resume',
        payload: { action: approval, approved: approval === 'APPROVE' }
      };
    }

    const formIds: Record<string, string> = {
      ACCOUNT_SETUP_FORM: 'ACCOUNT_SETUP',
      JOINT_OWNER_FORM: 'JOINT_OWNER_DETAILS',
      PROFILE_DATA_CAPTURE: 'PROFILE_DATA_CAPTURE',
      BENEFICIARY_CAPTURE: 'BENEFICIARY_CAPTURE',
      RISK_ASSESSMENT_FORM: 'RISK_ASSESSMENT',
      PRODUCT_FEATURES_FORM: 'PRODUCT_FEATURES'
    };
    const formId = ui?.widgetId ? formIds[ui.widgetId] : undefined;
    if (formId) {
      return this.formSubmission({ ...payload, formId });
    }

    const details = Object.entries(payload)
      .map(([key, value]) =>
        `${key.replace(/([A-Z])/g, ' $1').toLowerCase()}: ${String(value)}`
      )
      .join(', ');
    return {
      type: 'message',
      text: `Here are the requested account-opening details: ${details}`
    };
  }

  private formSubmission(value: Record<string, unknown>): WidgetCommand {
    return {
      type: 'message',
      text: 'POC_FORM_SUBMISSION:' + JSON.stringify(value)
    };
  }
}
