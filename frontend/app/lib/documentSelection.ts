/**
 * What the interface will accept before it asks the backend anything.
 *
 * Every rule here is also enforced server-side. It is repeated in the browser
 * so a clinician who selects a folder is told immediately, rather than after
 * uploading it - and so the refusal arrives while it is still obvious which
 * document caused it. The backend's own refusal cannot name the file, by
 * design, so a batch rejected server-side leaves nothing to act on.
 */

export const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt'] as const

const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
])

/**
 * Mirrors the default of MAX_BATCH_FILES in the backend, which is settable per
 * deployment. A deployment that lowers it will refuse a batch this accepts.
 */
export const MAX_FILES = 20

/** Mirrors MAX_FILE_SIZE_BYTES in the backend. */
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

export interface SelectedDocument {
  /** Stable across re-renders. Two documents can share a filename. */
  id: string
  file: File
}

function hasAllowedExtension(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  return (ALLOWED_EXTENSIONS as readonly string[]).includes(extension)
}

export function isAccepted(file: File): boolean {
  return hasAllowedExtension(file) && ALLOWED_MIME_TYPES.has(file.type)
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

  if (files.some(file => file.size > MAX_FILE_SIZE_BYTES)) {
    const megabytes = MAX_FILE_SIZE_BYTES / (1024 * 1024)
    return `Document trop volumineux. Maximum : ${megabytes} Mo par document.`
  }

  // An allowed extension carrying an unexpected type is worth its own wording:
  // the browser supplies the type, and it reports nothing useful for a DOCX on
  // a machine with no Office registration. Telling that clinician the format is
  // wrong would be false - it is the format the interface cannot confirm.
  if (files.some(file => hasAllowedExtension(file) && !ALLOWED_MIME_TYPES.has(file.type))) {
    return "Format non reconnu par le navigateur. Rouvrez le document et réenregistrez-le, ou choisissez-en un autre."
  }

  if (!files.every(isAccepted)) {
    return 'Type de fichier invalide. Formats acceptés : PDF, DOCX ou TXT.'
  }

  return null
}
