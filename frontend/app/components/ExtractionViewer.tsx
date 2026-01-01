'use client'

interface EntityDetail {
  text: string
  label: string
  score: number
  start: number
  end: number
}

interface ExtractedEntities {
  patient_info: EntityDetail[]
  anatomy: EntityDetail[]
  symptoms: EntityDetail[]
  examinations: EntityDetail[]
  treatments: EntityDetail[]
  pathologies: EntityDetail[]
  temporal: EntityDetail[]
  measurements: EntityDetail[]
  other: EntityDetail[]
}

interface Props {
  data: {
    file_id: string
    text: string
    extracted_entities: ExtractedEntities
    processed_at?: string | null
    mapping_info?: {
      language: string
      dataset: string
      description: string
    }
  }
}

export default function ExtractionViewer({ data }: Props) {
  const { extracted_entities, mapping_info } = data

  const categories = [
    { key: 'patient_info', label: 'Patient Info', entities: extracted_entities.patient_info },
    { key: 'anatomy', label: 'Anatomy', entities: extracted_entities.anatomy },
    { key: 'symptoms', label: 'Symptoms', entities: extracted_entities.symptoms },
    { key: 'examinations', label: 'Examinations', entities: extracted_entities.examinations },
    { key: 'treatments', label: 'Treatments', entities: extracted_entities.treatments },
    { key: 'pathologies', label: 'Pathologies', entities: extracted_entities.pathologies },
    { key: 'temporal', label: 'Temporal', entities: extracted_entities.temporal },
    { key: 'measurements', label: 'Measurements', entities: extracted_entities.measurements },
    { key: 'other', label: 'Other', entities: extracted_entities.other },
  ]

  return (
    <div className="mt-6 p-4 border rounded bg-gray-50">
      {mapping_info && (
        <div className="text-xs text-gray-500 mb-3">
          Model: {mapping_info.language} - {mapping_info.dataset}
        </div>
      )}

      <div>
        <h3 className="text-lg font-medium mb-3">Extracted Entities</h3>
        <div className="space-y-4">
          {categories.map(({ key, label, entities }) => {
            const filtered = entities.filter(e => e.text.length > 1)
            if (filtered.length === 0) return null

            return (
              <div key={key}>
                <h4 className="font-semibold text-gray-800 mb-1">{label}:</h4>
                <ul className="list-none ml-4 text-sm text-gray-700 space-y-1">
                  {filtered.map((entity, idx) => (
                    <li key={idx}>
                      - {entity.text} <span className="text-gray-500">({Math.round(entity.score * 100)}%)</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
