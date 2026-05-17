import React, { createContext, useContext, useState, useEffect } from 'react';

const COOKIE_KEY = 'plhall_lang';

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function persistLang(lang) {
  document.cookie = `${COOKIE_KEY}=${lang}; path=/; max-age=2592000; samesite=lax`;
}

// Fallback for local dev where middleware doesn't run
async function detectLanguageFromIP() {
  const SESSION_KEY = 'plhall_lang_detected';
  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) return cached;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);
    const res = await fetch('https://api.country.is/', { signal: controller.signal });
    clearTimeout(timer);
    const data = await res.json();
    const lang = data.country === 'CN' ? 'zh' : 'en';
    sessionStorage.setItem(SESSION_KEY, lang);
    return lang;
  } catch {
    return 'en';
  }
}

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used within LanguageProvider');
  return context;
};

export const LanguageProvider = ({ children }) => {
  // On Vercel: middleware already set the cookie before JS executes → no flash.
  // Local dev: cookie is absent, falls back to async IP detection below.
  const [language, setLanguage] = useState(() => getCookie(COOKIE_KEY) || 'en');

  useEffect(() => {
    if (getCookie(COOKIE_KEY)) return; // cookie present (Vercel path), skip detection

    // Local dev fallback: async IP detection
    detectLanguageFromIP().then(detected => {
      persistLang(detected);
      setLanguage(detected);
    });
  }, []);

  const toggleLanguage = () => {
    setLanguage(prev => {
      const next = prev === 'zh' ? 'en' : 'zh';
      persistLang(next); // write cookie so middleware sees it on next request
      return next;
    });
  };

  return (
    <LanguageContext.Provider value={{ language, toggleLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
};
