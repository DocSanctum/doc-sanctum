import pluginVue from 'eslint-plugin-vue'
import tseslint from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'
import vueParser from 'vue-eslint-parser'

export default [
  {
    ignores: ['dist/', 'node_modules/'],
  },
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: { parser: tsParser },
    },
    plugins: { vue: pluginVue },
    rules: {
      ...pluginVue.configs['vue3-recommended'].rules,
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    files: ['src/**/*.ts'],
    languageOptions: { parser: tsParser },
    plugins: { '@typescript-eslint': tseslint },
    rules: {
      ...tseslint.configs.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
]
