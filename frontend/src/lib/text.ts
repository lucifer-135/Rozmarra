/**
 * Splits a text after its first sentence. English sentences end with ".", "?" or "!", and Hindi
 * sentences end with "।". A full stop inside a number, such as "2.5", is not followed by a space,
 * so it does not end a sentence.
 */
export function splitFirstSentence(text: string): [string, string] {
  const match = /[.?!।](?=\s)/.exec(text)
  if (!match) return [text, '']
  const end = match.index + 1
  return [text.slice(0, end), text.slice(end).trim()]
}
