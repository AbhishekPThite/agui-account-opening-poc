import { Type } from '@angular/core';
import { AgentWidgetInstance } from '../models/agent-ui.model';
import { AccountSummaryComponent } from './account-summary.component';
import { DraftConfirmationComponent } from './draft-confirmation.component';
import { DynamicFormComponent } from './dynamic-form.component';
import { InformationAlertComponent } from './information-alert.component';
import { ProfileAssessmentComponent } from './profile-assessment.component';

export const WIDGET_REGISTRY: Record<string, Type<AgentWidgetInstance>> = {
  JOINT_OWNER_FORM: DynamicFormComponent,
  ACCOUNT_SETUP_FORM: DynamicFormComponent,
  PROFILE_DATA_CAPTURE: DynamicFormComponent,
  BENEFICIARY_CAPTURE: DynamicFormComponent,
  PRODUCT_FEATURES_FORM: DynamicFormComponent,
  APPLICATION_SUMMARY: AccountSummaryComponent,
  DRAFT_CONFIRMATION: DraftConfirmationComponent,
  INFORMATION_ALERT: InformationAlertComponent,
  PROFILE_ASSESSMENT: ProfileAssessmentComponent,
  RISK_ASSESSMENT_FORM: DynamicFormComponent
};
