export default {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  moduleFileExtensions: ['js', 'jsx', 'json'],
  transform: {
    '^.+\\.(js|jsx)$': ['babel-jest', {
      presets: [
        ['@babel/preset-env', { targets: { node: 'current' } }],
        ['@babel/preset-react', { runtime: 'automatic' }],
      ],
    }],
  },
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.test.(js|jsx)',
    '<rootDir>/src/**/?(*.)(spec|test).(js|jsx)',
  ],
  // The key is moduleNameMapper. It was spelled moduleNameMapping, which Jest
  // ignores, so the CSS stub was never actually applied.
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
};
