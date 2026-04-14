import React from 'react';
import { Button } from "@/components/ui/button";
import { Languages } from 'lucide-react';
import { useLanguage } from './LanguageContext';

export default function LanguageToggle() {
  const { language, toggleLanguage } = useLanguage();

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      className="gap-2 bg-white/90 backdrop-blur-sm border-white/30 hover:bg-white text-[#37003c] font-semibold"
    >
      <Languages className="w-4 h-4" />
      {language === 'zh' ? 'EN' : '中文'}
    </Button>
  );
}