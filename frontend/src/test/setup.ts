import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/') // the open chat lives in the URL hash
})

// jsdom does not implement these browser APIs used by the UI.
Element.prototype.scrollIntoView ??= function scrollIntoView() {}
window.matchMedia ??= ((query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent: () => false,
  }) as MediaQueryList)
