/** Listas editadas como texto: palabras clave separadas por comas y frases, una por línea. */
export const splitComma = (text: string) => text.split(',').map((v) => v.trim()).filter(Boolean)
export const splitLines = (text: string) => text.split('\n').map((v) => v.trim()).filter(Boolean)
