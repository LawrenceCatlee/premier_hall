import React from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Users, Star } from 'lucide-react';
import { cn } from "@/lib/utils";
import { useLanguage } from '../LanguageContext';
import { translations, clubNameMap } from '../translations';

/**
 * Format a single achievement as a plain-text sentence.
 * detail formats coming from the backend:
 *   出场250次  → "653场"
 *   单队200场  → "切尔西|429"  (team|apps)
 *   百球       → "177"
 *   百大零封   → "100"
 *   三冠王     → "1992–93, 1993–94, ..."
 *   金靴奖     → "1994, 1995, 1996"
 *   金手套奖   → "2004–05, 2005–06"
 *   年度最佳   → "2004"
 *   最佳阵容   → "10年" | "20年"
 */
function formatAchievement(type, detail, language) {
  const joinDot = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean).join('、');

  if (language === 'zh') {
    switch (type) {
      case '出场250次':
        return `在英超出场了${detail.replace('场', '')}场`;
      case '单队200场': {
        const [team, apps] = detail.split('|');
        return `为${team}出场${apps}场英超比赛`;
      }
      case '百球':
        return `英超共打入${detail}球`;
      case '百大零封':
        return `英超共零封${detail}次`;
      case '三冠王': {
        const seasons = joinDot(detail);
        return `英超冠军：${seasons}`;
      }
      case '金靴奖': {
        const years = joinDot(detail);
        return `英超射手王：${years}`;
      }
      case '金手套奖': {
        const years = joinDot(detail);
        return `英超最佳门将奖：${years}`;
      }
      case '年度最佳': {
        const years = joinDot(detail);
        return years ? `英超年度最佳：${years}` : '英超年度最佳';
      }
      case '最佳阵容':
        return `入选英超${detail}最佳阵容`;
      default:
        return detail ? `${type}：${detail}` : type;
    }
  } else {
    // English
    switch (type) {
      case '出场250次':
        return `${detail.replace('场', '')} Premier League appearances`;
      case '单队200场': {
        const [team, apps] = detail.split('|');
        return `${apps} PL apps for ${clubNameMap[team] || team}`;
      }
      case '百球':
        return `${detail} Premier League goals`;
      case '百大零封':
        return `${detail} Premier League clean sheets`;
      case '三冠王': {
        const seasons = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `PL Champion: ${seasons}`;
      }
      case '金靴奖': {
        const years = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `Golden Boot: ${years}`;
      }
      case '金手套奖': {
        const years = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `Golden Glove: ${years}`;
      }
      case '年度最佳': {
        const years = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return years ? `Player of the Year: ${years}` : 'Player of the Year';
      }
      case '最佳阵容':
        return `PL ${detail} Team of the Year`;
      default:
        return detail ? `${type}: ${detail}` : type;
    }
  }
}

export default function PlayerCard({ player, showGap = false }) {
  const { language } = useLanguage();
  const t = translations[language];

  const isHoF = player.is_hall_of_fame;
  const isActive = player.is_active;

  const borderColor = isHoF
    ? 'border-[#FFD700] shadow-[#FFD700]/40'
    : isActive
    ? 'border-[#ff2882] shadow-[#ff2882]/30'
    : 'border-slate-200';

  // Normalise achievements: support both old string[] and new {type,detail}[]
  const achievements = (player.achievements || []).map(a =>
    typeof a === 'string' ? { type: a, detail: '' } : a
  );

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
            {isHoF && (
              <Badge className="bg-[#FFD700] hover:bg-[#FFD700]/90 text-slate-900 font-bold text-xs">
                <Trophy className="w-3 h-3 mr-1" />
                {t.hallOfFame}
              </Badge>
            )}
            {isActive && (
              <Badge className="bg-[#ff2882] hover:bg-[#ff2882]/90 text-white font-bold text-xs">
                {t.active}
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-2">
          {/* Clubs */}
          <div className="flex items-start gap-2 text-sm">
            <Users className="w-4 h-4 text-[#37003c] flex-shrink-0 mt-0.5" />
            <p className="text-slate-600">
              {language === 'en'
                ? player.clubs?.map(c => clubNameMap[c] || c).join(', ')
                : player.clubs?.join('、')}
            </p>
          </div>

          {/* Achievements — one plain-text sentence per line */}
          {achievements.length > 0 && (
            <div className="flex items-start gap-2 text-sm">
              <Star className="w-4 h-4 text-[#37003c] flex-shrink-0 mt-0.5" />
              <ul className="space-y-0.5">
                {achievements.map((a, idx) => (
                  <li key={idx} className="text-slate-700">
                    {formatAchievement(a.type, a.detail, language)}
                  </li>
                ))}
              </ul>
            </div>
          )}
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
