import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { LanguageProvider } from './components/LanguageContext';
import LanguageToggle from './components/LanguageToggle';

const NAV = [
  { path: '/',     label: '名人堂' },
  { path: '/News', label: '新闻快报' },
];

function TopNav() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav
      className="sticky top-0 z-50 flex items-center justify-between px-4 sm:px-6 py-2"
      style={{
        background: 'rgba(26,0,32,0.88)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      <div className="flex gap-1">
        {NAV.map(({ path, label }) => {
          const active = path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(path);
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
              style={active
                ? { background: '#FFD700', color: '#1a0020' }
                : { color: '#94a3b8' }
              }
            >
              {label}
            </button>
          );
        })}
      </div>
      <LanguageToggle />
    </nav>
  );
}

export default function Layout({ children }) {
  return (
    <LanguageProvider>
      <TopNav />
      {children}
    </LanguageProvider>
  );
}
