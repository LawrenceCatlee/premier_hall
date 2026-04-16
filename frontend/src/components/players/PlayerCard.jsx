import { Trophy, Users, Star, TrendingUp } from 'lucide-react';
import { cn } from "@/lib/utils";
import { useLanguage } from '../LanguageContext';
import { translations, clubNameMap } from '../translations';

const POSITION_LABEL = { G: 'GK', D: 'DEF', M: 'MID', F: 'FWD' };
const POSITION_COLOR = {
  G:  { bg: 'bg-amber-400/20',   text: 'text-amber-300'  },
  D:  { bg: 'bg-sky-400/20',     text: 'text-sky-300'    },
  M:  { bg: 'bg-emerald-400/20', text: 'text-emerald-300'},
  F:  { bg: 'bg-rose-400/20',    text: 'text-rose-300'   },
};

function formatAchievement(type, detail, language) {
  const joinDot = (str) =>
    (str || '').split(',').map(s => s.trim()).filter(Boolean).join('、');

  if (language === 'zh') {
    switch (type) {
      case '出场250次':
        return `在英超出场了${detail.replace('场', '')}场`;
      case '单队200场': {
        const [team, apps] = (detail || '').split('|');
        return `为${team}出场${apps}场英超比赛`;
      }
      case '百球':
        return `英超共打入${detail}球`;
      case '百大零封':
        return `英超共零封${detail}次`;
      case '三冠王':
        return `英超冠军：${joinDot(detail)}`;
      case '金靴奖':
        return `英超射手王：${joinDot(detail)}`;
      case '金手套奖':
        return `英超最佳门将奖：${joinDot(detail)}`;
      case '年度最佳': {
        const y = joinDot(detail);
        return y ? `英超年度最佳：${y}` : '英超年度最佳';
      }
      case '最佳阵容':
        return `入选英超${detail}最佳阵容`;
      default:
        return detail ? `${type}：${detail}` : type;
    }
  } else {
    switch (type) {
      case '出场250次':
        return `${detail.replace('场', '')} PL Appearances`;
      case '单队200场': {
        const [team, apps] = (detail || '').split('|');
        return `${apps} PL apps for ${clubNameMap[team] || team}`;
      }
      case '百球':
        return `${detail} PL Goals`;
      case '百大零封':
        return `${detail} PL Clean Sheets`;
      case '三冠王': {
        const s = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `PL Champion: ${s}`;
      }
      case '金靴奖': {
        const y = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `Golden Boot: ${y}`;
      }
      case '金手套奖': {
        const y = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return `Golden Glove: ${y}`;
      }
      case '年度最佳': {
        const y = (detail || '').split(',').map(s => s.trim()).filter(Boolean).join(', ');
        return y ? `Player of Year: ${y}` : 'Player of Year';
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

  const isHoF    = player.is_hall_of_fame;
  const isActive = player.is_active;
  const pos      = (player.position || '').toUpperCase().charAt(0);
  const posLabel = POSITION_LABEL[pos] || pos;
  const posStyle = POSITION_COLOR[pos] || { bg: 'bg-slate-400/20', text: 'text-slate-300' };

  // Accent colour
  const accentColor = isHoF ? '#FFD700' : isActive ? '#ff2882' : '#475569';

  // Achievements: normalise old string[] to {type,detail}[]
  const achievements = (player.achievements || []).map(a =>
    typeof a === 'string' ? { type: a, detail: '' } : a
  );

  // Near-miss gap items (provided by HallOfFame.jsx)
  const gapItems = player.gap_items || [];

  return (
    <div
      className={cn(
        'rounded-2xl overflow-hidden flex flex-col',
        'bg-white/5 backdrop-blur-sm',
        'border transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl'
      )}
      style={{ borderColor: `${accentColor}55` }}
    >
      {/* Accent top bar */}
      <div className="h-1 w-full" style={{ background: accentColor }} />

      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Header: name + badges */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-bold text-white leading-snug truncate">
              {language === 'zh' ? player.name_cn : player.name_en}
            </h3>
            {language === 'zh' && player.name_cn !== player.name_en && (
              <p className="text-xs text-slate-400 truncate">{player.name_en}</p>
            )}
          </div>
          <div className="flex flex-col gap-1 items-end shrink-0">
            {isHoF && (
              <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/40">
                <Trophy className="w-2.5 h-2.5" />{t.hallOfFame}
              </span>
            )}
            {isActive && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#ff2882]/20 text-[#ff2882] border border-[#ff2882]/40">
                {t.active}
              </span>
            )}
            {posLabel && (
              <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded-full', posStyle.bg, posStyle.text)}>
                {posLabel}
              </span>
            )}
          </div>
        </div>

        {/* Clubs */}
        {player.clubs && player.clubs.length > 0 && (
          <div className="flex items-start gap-1.5 text-xs text-slate-300">
            <Users className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
            <span>
              {language === 'en'
                ? player.clubs.map(c => clubNameMap[c] || c).join(' · ')
                : player.clubs.join(' · ')}
            </span>
          </div>
        )}

        {/* Achievements */}
        {achievements.length > 0 && (
          <div className="flex items-start gap-1.5">
            <Star className="w-3.5 h-3.5 text-[#FFD700]/70 shrink-0 mt-0.5" />
            <ul className="space-y-0.5 flex-1">
              {achievements.map((a, i) => (
                <li key={i} className="text-xs text-slate-200 leading-relaxed">
                  {formatAchievement(a.type, a.detail, language)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Near-miss gaps */}
        {showGap && gapItems.length > 0 && (
          <div className="mt-auto pt-2 border-t border-white/10 flex items-start gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-[#ff2882] shrink-0 mt-0.5" />
            <ul className="space-y-0.5 flex-1">
              {gapItems.map((item, i) => (
                <li key={i} className="text-xs text-[#ff2882]/90 leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
