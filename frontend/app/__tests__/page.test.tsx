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

function selectFiles(count = 1, type = 'text/plain') {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const files = Array.from(
    { length: count },
    (_, index) => new File(['content'], `report${index}.txt`, { type })
  )
  fireEvent.change(input, { target: { files } })
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: /^Résumer / }))
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
    submit()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(mockedAxios.post.mock.calls[0][0]).toContain('/api/analyze')
    expect(await screen.findByText('fièvre')).toBeInTheDocument()
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('asks the backend nothing until the clinician submits', () => {
    render(<HomePage />)
    selectFiles(2)

    expect(mockedAxios.post).not.toHaveBeenCalled()
    expect(screen.getByText('2 documents prêts')).toBeInTheDocument()
  })

  it('posts every document under the field the API reads', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles(3)
    submit()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(3)
  })

  it('refuses an unsupported document without asking the backend', () => {
    render(<HomePage />)
    selectFiles(1, 'image/png')

    expect(mockedAxios.post).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/PDF, DOCX ou TXT/)
    expect(screen.queryByRole('button', { name: /^Résumer / })).not.toBeInTheDocument()
  })

  it('drops a document from the batch before submitting', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles(2)
    fireEvent.click(screen.getByRole('button', { name: 'Retirer report0.txt' }))
    submit()

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(1)
  })

  it('never stores and never issues an id', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles()
    submit()

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
    submit()

    expect(await screen.findByText(/Lecture du document/)).toBeInTheDocument()

    settle(analysisResponse)
    await waitFor(() =>
      expect(screen.queryByText(/Lecture du document/)).not.toBeInTheDocument()
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
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to extract text from the document.'
    )
  })

  it('keeps the batch so a failed analysis can be retried', async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: { message: 'Internal server error' } } },
    })

    render(<HomePage />)
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    mockedAxios.post.mockResolvedValue(analysisResponse)
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledTimes(2))
    expect((mockedAxios.post.mock.calls[1][1] as FormData).getAll('files')).toHaveLength(2)
  })

  it('clears a previous summary when starting over', async () => {
    mockedAxios.post.mockResolvedValue(analysisResponse)

    render(<HomePage />)
    selectFiles()
    submit()
    expect(await screen.findByText('fièvre')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Nouveau résumé' }))

    await waitFor(() => expect(screen.queryByText('fièvre')).not.toBeInTheDocument())
    expect(screen.queryByText(/documents prêts/)).not.toBeInTheDocument()
  })
})
