import { ref } from 'vue'
import { i18n, type SupportedLocale } from '../i18n'
import { api } from '../services/api'

const STORAGE_KEY = 'ds-locale'

const locale = ref<SupportedLocale>('en')

function isSupportedLocale(value: string | null): value is SupportedLocale {
  return value === 'ko' || value === 'en'
}

function browserLocale(): SupportedLocale {
  return navigator.language.toLowerCase().startsWith('ko') ? 'ko' : 'en'
}

function apply(value: SupportedLocale) {
  locale.value = value
  i18n.global.locale.value = value
}

async function initLocale() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (isSupportedLocale(stored)) {
    apply(stored)
    return
  }

  let detected: SupportedLocale
  try {
    const result = await api.getLocale()
    detected = result.locale === 'ko' || result.locale === 'en' ? result.locale : browserLocale()
  } catch {
    detected = browserLocale()
  }

  apply(detected)
  localStorage.setItem(STORAGE_KEY, detected)
}

function setLocale(value: SupportedLocale) {
  apply(value)
  localStorage.setItem(STORAGE_KEY, value)
}

export function useLocale() {
  return { locale, initLocale, setLocale }
}
