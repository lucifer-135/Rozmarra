import { expect, test } from 'vitest'
import { splitFirstSentence } from './text'

test('an English text splits after its first sentence', () => {
  expect(splitFirstSentence('The twin is a model. It has three parts.')).toEqual([
    'The twin is a model.',
    'It has three parts.',
  ])
})

test('a Hindi text splits after the first danda', () => {
  expect(splitFirstSentence('यह पहला वाक्य है। यह दूसरा वाक्य है।')).toEqual([
    'यह पहला वाक्य है।',
    'यह दूसरा वाक्य है।',
  ])
})

test('a full stop inside a number does not end a sentence', () => {
  expect(splitFirstSentence('The score is 2.5 points. It is low.')).toEqual([
    'The score is 2.5 points.',
    'It is low.',
  ])
})

test('a text with one sentence has nothing to fold', () => {
  expect(splitFirstSentence('Only one sentence.')).toEqual(['Only one sentence.', ''])
})
