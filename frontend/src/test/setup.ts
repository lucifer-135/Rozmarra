import '@testing-library/jest-dom/vitest'
import '@/i18n'

// The test browser (jsdom) has no ResizeObserver, which the Radix components use.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
