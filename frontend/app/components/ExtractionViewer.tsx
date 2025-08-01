'use client'

interface Props {
  data: {
    file_id: string
    text: string
    extracted_entities: {
      diseases: string[]
      symptoms: string[]
      treatments: string[]
    }
  }
}

export default function ExtractionViewer({ data }: Props) {
  const { text, extracted_entities } = data
  return (
    <div className="mt-6 p-4 border rounded bg-gray-50">
      <h2 className="text-xl font-semibold mb-2">Extracted Text</h2>
      <p className="text-sm whitespace-pre-line mb-4">{text}</p>

      <div>
        <h3 className="text-lg font-medium">Entities</h3>
        <div className="mt-2 space-y-1">
          <EntityList title="Diseases" items={extracted_entities.diseases} />
          <EntityList title="Symptoms" items={extracted_entities.symptoms} />
          <EntityList title="Treatments" items={extracted_entities.treatments} />
        </div>
      </div>
    </div>
  )
}

function EntityList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="font-semibold text-gray-800">{title}:</h4>
      <ul className="list-disc ml-5 text-sm text-gray-700">
        {items.length > 0 ? (
          items.map((item, idx) => <li key={idx}>{item}</li>)
        ) : (
          <li className="italic text-gray-500">None found</li>
        )}
      </ul>
    </div>
  )
}
