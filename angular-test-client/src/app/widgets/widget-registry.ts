import { Type } from '@angular/core';
import { AgentWidgetInstance } from '../models/agent-ui.model';
import {
  AccountSummaryComponent,
  DraftConfirmationComponent,
  DynamicFormComponent,
  InformationAlertComponent,
  ProfileAssessmentComponent
} from './widget-components';

export const WIDGET_REGISTRY: Record<string, Type<AgentWidgetInstance>> = {
  JOINT_OWNER_FORM: DynamicFormComponent,
  ACCOUNT_SETUP_FORM: DynamicFormComponent,
  APPLICATION_SUMMARY: AccountSummaryComponent,
  DRAFT_CONFIRMATION: DraftConfirmationComponent,
  INFORMATION_ALERT: InformationAlertComponent,
  PROFILE_ASSESSMENT: ProfileAssessmentComponent
};
