import React from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Users, Award } from 'lucide-react';
import { cn } from "@/lib/utils";
import { useLanguage } from '../LanguageContext';
import { translations, clubNameMap, achievementMap } from '../translations';

export default function PlayerCard({ player, showGap = false }) {
  const { language } = useLanguage();
  const t = translations[language];
  
  const borderColor = player.is_hall_of_fame 
    ? 'border-[#00ff85] shadow-[#00ff85]/30' 
    : player.is_active 
    ? 'border-[#ff2882] shadow-[#ff2882]/30' 
    : 'border-slate-200';

  return (
    <Card className={cn(
      "overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1",
      "border-2",
      borderColor
    )}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-xl font-bold text-slate-900">
            {language === 'zh' ? player.name_cn : player.name_en}
          </h3>
          <div className="flex flex-col gap-1 ml-2 flex-shrink-0">
            {player.is_hall_of_fame && (
              <Badge className="bg-[#00ff85] hover:bg-[#00ff85]/90 text-[#37003c] font-bold text-xs">
                <Trophy className="w-3 h-3 mr-1" />
                {t.hallOfFame}
              </Badge>
            )}
            {player.is_active && (
              <Badge className="bg-[#ff2882] hover:bg-[#ff2882]/90 text-white font-bold text-xs">
                {t.active}
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-start gap-2 text-sm">
            <Users className="w-4 h-4 text-[#37003c] flex-shrink-0 mt-0.5" />
            <p className="text-slate-600">
              {language === 'en'
                ? player.clubs?.map(c => clubNameMap[c] || c).join(', ')
                : player.clubs?.join('、')}
            </p>
          </div>

          <div className="flex items-start gap-2 text-sm">
            <Award className="w-4 h-4 text-[#37003c] flex-shrink-0 mt-0.5" />
            <div className="flex flex-wrap gap-1">
              {player.achievements?.map((achievement, idx) => {
                const label = language === 'en' ? (achievementMap[achievement] || achievement) : achievement;
                return (
                  <Badge key={idx} variant="secondary" className="text-xs">
                    {label}
                  </Badge>
                );
              })}
            </div>
          </div>
        </div>

        {showGap && player.gap_info && (
          <div className="mt-3 pt-3 border-t border-slate-200">
            <p className="text-sm font-medium text-[#ff2882]">
              {player.gap_info}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}