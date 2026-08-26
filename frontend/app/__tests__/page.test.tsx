import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import axios from 'axios'
import HomePage from '../page'

vi.mock('axios')

const mockedAxios = vi.mocked(axios, true)

const analysisResponse = {
  status: 200,
  data: {
    summary: {
      patient: 'Patient, 67 ans, homme.',
      sections: [
        {
          key: 'symptoms',
          heading: 'Signes et symptômes',
          sentence: 'Fièvre.',
          findings: ['fièvre'],
        },
      ],
      document_count: 1,
      empty: false,
    },
    documents: [],
    retained: false,
  },
}

function selectFiles(count = 1) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const files = Array.from(
    { length: count },
    (_, index) => new File(['content'], `report${index}.txt`, { type: 'text/plain' })
  )
  fireEvent.change(input, { target: { files } })
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

  it('summarises the selected documents', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(mockedAxios.post.mock.calls[0][0]).toContain('/api/analyze')
    expect(await screen.findByText('Fièvre.')).toBeInTheDocument()
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('posts every document under the field the API reads', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles(3)

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(3)
  })

  it('never stores and never issues an id', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(mockedAxios.post.mock.calls[0][0]).not.toContain('/api/upload')
    expect(screen.queryByText(/File ID/)).not.toBeInTheDocument()
  })

  it('offers no storage, retention or masking controls', () => {
    render(<HomePage />)

    // The clinician is asked for documents, not for a data-handling policy.
    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
    expect(screen.queryByText(/serveur|supprim|masqu/i)).not.toBeInTheDocument()
  })

  it('shows progress while the analysis runs', async () => {
    let settle: (value: unknown) => void = () => {}
    mockedAxios.post.mockReturnValue(new Promise(resolve => (settle = resolve)))

    render(<HomePage />)
    selectFiles()

    expect(await screen.findByText(/Analyse en cours/)).toBeInTheDocument()

    settle(analysisResponse)
    await waitFor(() =>
      expect(screen.queryByText(/Analyse en cours/)).not.toBeInTheDocument()
    )
  })

  it('surfaces the API error message', async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: {
        data: { detail: { message: 'Unable to extract text from the document.' } },
      },
    })

    render(<HomePage />)
    selectFiles()

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent('Unable to extract text from the document.')
  })

  it('clears a previous summary before a new analysis', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles()
    expect(await screen.findByText('Fièvre.')).toBeInTheDocument()

    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: { message: 'Unable to extract text from the document.' } } },
    })
    selectFiles()

    await waitFor(() => expect(screen.queryByText('Fièvre.')).not.toBeInTheDocument())
  })
})
