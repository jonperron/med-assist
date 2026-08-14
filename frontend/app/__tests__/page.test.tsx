import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import axios from 'axios'
import HomePage from '../page'

vi.mock('axios')

const mockedAxios = vi.mocked(axios, true)

const emptyEntities = {
  patient_info: [],
  anatomy: [],
  symptoms: [],
  examinations: [],
  treatments: [],
  pathologies: [],
  temporal: [],
  measurements: [],
  other: [],
}

const analysisResponse = {
  status: 200,
  data: {
    text: 'Le patient présente une fièvre.',
    extracted_entities: {
      ...emptyEntities,
      symptoms: [{ text: 'fièvre', label: 'sosy', score: 0.9, start: 26, end: 32 }],
    },
    pseudonymized: false,
    retained: false,
  },
}

function selectFile() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const file = new File(['content'], 'report.txt', { type: 'text/plain' })
  fireEvent.change(input, { target: { files: [file] } })
}

function postedForm() {
  return mockedAxios.post.mock.calls[0][1] as FormData
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedAxios.isAxiosError.mockImplementation(
      (error: unknown) => Boolean((error as { isAxiosError?: boolean })?.isAxiosError)
    )
  })

  it('analyzes without storing by default', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFile()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(mockedAxios.post.mock.calls[0][0]).toContain('/api/analyze')
    expect(await screen.findByText(/fièvre/)).toBeInTheDocument()
  })

  it('issues no file id on the stateless path', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFile()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(screen.queryByText(/File ID:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Delete Now/)).not.toBeInTheDocument()
  })

  it('uploads for later when the user opts into storage', async () => {
    mockedAxios.post.mockResolvedValue({
      status: 200,
      data: { file_id: 'abc', expires_in_seconds: 3600 },
    })

    render(<HomePage />)
    fireEvent.click(
      screen.getByLabelText(/Keep the document on the server/)
    )
    selectFile()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(mockedAxios.post.mock.calls[0][0]).toContain('/api/upload_document/')
    expect(await screen.findByText(/File ID: abc/)).toBeInTheDocument()
  })

  it('forwards the pseudonymisation choice', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    fireEvent.click(screen.getByLabelText(/Mask detected patient identifiers/))
    selectFile()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(postedForm().get('pseudonymize')).toBe('true')
  })

  it('defaults pseudonymisation to false', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFile()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(postedForm().get('pseudonymize')).toBe('false')
  })

  it('renders entities even when no text came back', async () => {
    mockedAxios.post.mockResolvedValue({
      status: 200,
      data: { file_id: 'abc', expires_in_seconds: 3600 },
    })
    mockedAxios.get.mockResolvedValue({
      status: 200,
      data: {
        file_id: 'abc',
        text: null,
        extracted_entities: {
          ...emptyEntities,
          pathologies: [{ text: 'grippe', label: 'pathologie', score: 0.9 }],
        },
        expires_in_seconds: 3500,
      },
    })

    render(<HomePage />)
    fireEvent.click(screen.getByLabelText(/Keep the document on the server/))
    selectFile()

    fireEvent.click(await screen.findByText('Extract Text'))

    expect(await screen.findByText(/grippe/)).toBeInTheDocument()
    expect(screen.getByText(/document text is not kept/)).toBeInTheDocument()
  })

  it('surfaces the API error message', async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: { message: 'Unable to extract text from the document.' } } },
    })

    render(<HomePage />)
    selectFile()

    expect(
      await screen.findByText('Unable to extract text from the document.')
    ).toBeInTheDocument()
  })
})
