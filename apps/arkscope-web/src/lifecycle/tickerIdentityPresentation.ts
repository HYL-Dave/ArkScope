import type {
  TickerIdentityTransitionActivityChangeType,
  TickerIdentityTransitionActivityType,
  TickerIdentityTransitionApprovalAuthority,
  TickerIdentityTransitionBlockReason,
  TickerIdentityTransitionCaveat,
  TickerIdentityTransitionKind,
  TickerIdentityTransitionStatus,
} from "../api";

function closedLabel<Value extends string>(
  value: string,
  labels: Record<Value, string>,
  unknownValue: string,
): string {
  return Object.prototype.hasOwnProperty.call(labels, value)
    ? labels[value as Value]
    : unknownValue;
}

export function tickerTransitionStatusLabel(
  value: string,
  labels: Record<TickerIdentityTransitionStatus, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionActivityTypeLabel(
  value: string,
  labels: Record<TickerIdentityTransitionActivityType, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionApprovalAuthorityLabel(
  value: string,
  labels: Record<TickerIdentityTransitionApprovalAuthority, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionActivityChangeLabel(
  value: string,
  labels: Record<TickerIdentityTransitionActivityChangeType, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionKindLabel(
  value: string,
  labels: Record<TickerIdentityTransitionKind, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionBlockReasonLabel(
  value: string,
  labels: Record<TickerIdentityTransitionBlockReason, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}

export function tickerTransitionCaveatLabel(
  value: string,
  labels: Record<TickerIdentityTransitionCaveat, string>,
  unknownValue: string,
): string {
  return closedLabel(value, labels, unknownValue);
}
