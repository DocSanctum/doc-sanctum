import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import './style.css'
import './composables/useTheme'
import { i18n } from './i18n'
import { useLocale } from './composables/useLocale'

async function bootstrap() {
  await useLocale().initLocale()
  createApp(App).use(VueQueryPlugin).use(i18n).mount('#app')
}

bootstrap()
