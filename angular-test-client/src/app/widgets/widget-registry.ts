import { Type } from '@angular/core';
import {
  AccountSummaryComponent,
  DraftConfirmationComponent,
  DynamicFormComponent,
  InformationAlertComponent
} from './widget-components';

export const WIDGET_REGISTRY: Record<string, Type<unknown>> = {
  JOINT_OWNER_FORM: DynamicFormComponent,
  APPLICATION_SUMMARY: AccountSummaryComponent,
  DRAFT_CONFIRMATION: DraftConfirmationComponent,
  INFORMATION_ALERT: InformationAlertComponent
};
