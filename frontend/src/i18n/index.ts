import { createI18n } from 'vue-i18n'
import { en } from './locales/en'
import { ko } from './locales/ko'

export type SupportedLocale = 'en' | 'ko'

export const i18n = createI18n({
  legacy: false,
  locale: 'en' as SupportedLocale,
  fallbackLocale: 'en' as SupportedLocale,
  messages: { en, ko },
})
