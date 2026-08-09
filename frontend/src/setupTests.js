import '@testing-library/jest-dom';

// jsdom provides neither, and both are used by the auth and streaming code.
if (!global.TextDecoder) {
  const { TextDecoder, TextEncoder } = require('util');
  global.TextDecoder = TextDecoder;
  global.TextEncoder = TextEncoder;
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
