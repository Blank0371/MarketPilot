import { mockCalculationResult, mockEditableFieldGroups } from "./mockData";
import type { CalculationResult, EditableFieldGroup } from "./types";

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Extract editable fields from a free-form business idea pitch.
 *
 * TODO: Replace with the real backend call, e.g.
 *   fetch('/api/extract', { method: 'POST', body: JSON.stringify({ pitchText }) })
 *     .then((r) => r.json())
 *
 * The mock currently ignores the pitch and returns the canonical demo groups.
 */
export async function extractFields(
  pitchText: string,
): Promise<EditableFieldGroup[]> {
  await delay(900);
  void pitchText;
  return structuredClone(mockEditableFieldGroups);
}

/**
 * Send the edited fields to the backend and receive the calculation result.
 *
 * TODO: Replace with the real backend call, e.g.
 *   fetch('/api/calculate', { method: 'POST', body: JSON.stringify({ groups }) })
 *     .then((r) => r.json())
 *
 * The mock currently ignores the input and returns the canonical demo result.
 */
export async function calculateResult(
  groups: EditableFieldGroup[],
): Promise<CalculationResult> {
  await delay(1100);
  void groups;
  return structuredClone(mockCalculationResult);
}
