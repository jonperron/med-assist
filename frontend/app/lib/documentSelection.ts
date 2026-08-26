/**
 * What the interface will accept before it asks the backend anything.
 *
 * Every rule here is also enforced server-side. It is repeated in the browser
 * so a clinician who selects a folder is told immediately, rather than after
 * uploading it.
 */

export const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt'] as const

const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
])

/** Mirrors MAX_BATCH_FILES in the backend. */
export const MAX_FILES = 20

export interface SelectedDocument {
  /** Stable across re-renders. Two documents can share a filename. */
  id: string
  file: File
}

export function isAccepted(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  return (
    (ALLOWED_EXTENSIONS as readonly string[]).includes(extension) &&
    ALLOWED_MIME_TYPES.has(file.type)
  )
}

/**
 * Say why a selection cannot be added, or nothing when it can.
 *
 * The whole selection is refused rather than filtered: silently dropping a
 * document would produce a summary missing a source nobody was told about.
 */
export function describeRejection(files: File[], alreadySelected: number): string | null {
  if (alreadySelected + files.length > MAX_FILES) {
    return `Trop de documents à la fois. Maximum : ${MAX_FILES}.`
  }

  if (!files.every(isAccepted)) {
    return 'Type de fichier invalide. Formats acceptés : PDF, DOCX ou TXT.'
  }

  return null
}
