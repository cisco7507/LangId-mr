// Minimal CRA/Jest smoke test for the dashboard.
// Ensures the App component renders the header text.

import React from 'react';
import { render } from '@testing-library/react';
import App from './App.jsx';

it('renders LangID Job Dashboard header', () => {
  const { getByText } = render(<App />);
  expect(getByText(/LangID Job Dashboard/i)).toBeInTheDocument();
});
