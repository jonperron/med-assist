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
export type UploadResponse = components['schemas']['UploadResponse']
export type ErrorResponse = components['schemas']['ErrorResponse']

// The page shows whichever of the two analysis paths ran: /analyze answers
// without a file id, /get_extracted_text answers with one and may omit the
// text. Kept as a union rather than a merge, so reading a field only one of
// them has has to be narrowed first.
export type ExtractionData = ExtractionResponse | AnalysisResponse
