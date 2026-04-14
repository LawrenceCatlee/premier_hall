import React from 'react';
import { LanguageProvider } from './components/LanguageContext';

export default function Layout({ children }) {
  return (
    <LanguageProvider>
      {children}
    </LanguageProvider>
  );
}