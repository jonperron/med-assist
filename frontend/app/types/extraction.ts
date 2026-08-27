// The names the components use, pointing at the generated schema.
//
// api.ts is regenerated from backend/openapi.json with `npm run generate:types`;
// nothing here restates a field, so a backend rename breaks the build instead
// of quietly emptying a panel.
import type { components } from './api'

export type EntityDetail = components['schemas']['EntityDetail']
export type ExtractedEntities = components['schemas']['ExtractedEntities']
export type ExtractionResponse = components['schemas']['ExtractionResponse']
export type AnalysisResponse = components['schemas']['AnalysisResponse']
export type ClinicalSummary = components['schemas']['ClinicalSummary']
export type SummarySection = components['schemas']['SummarySection']
export type UploadResponse = components['schemas']['UploadResponse']
export type ErrorResponse = components['schemas']['ErrorResponse']
export type Finding = components['schemas']['Finding']
export type AnalyzedDocument = components['schemas']['AnalyzedDocument']
export type DateRange = components['schemas']['DateRange']
export type AnalysisEvent = components['schemas']['AnalysisEvent']
export type FailureReason = components['schemas']['FailureReason']
