import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import hi from './hi.json'

// All interface text lives in en.json and hi.json. Components must not contain
// hard-coded text. A native Hindi speaker reviews hi.json before the submission.
export const LANGUAGES = ['en', 'hi'] as const
export type Language = (typeof LANGUAGES)[number]

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
  },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
})

export default i18n
