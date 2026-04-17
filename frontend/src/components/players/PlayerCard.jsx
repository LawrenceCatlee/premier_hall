import { Building, Star, TrendingUp } from 'lucide-react';
import { cn } from "@/lib/utils";
import { useLanguage } from '../LanguageContext';
import { translations, clubNameMap, nationalityFlag, nationalityZh } from '../translations';

const POSITION_LABEL = { G: 'GK', D: 'DEF', M: 'MID', F: 'FWD' };
const POSITION_COLOR = {
  G:  { bg: 'bg-amber-400/20',   text: 'text-amber-300'  },
  D:  { bg: 'bg-sky-400/20',     text: 'text-sky-300'    },
  M:  { bg: 'bg-emerald-400/20', text: 'text-emerald-300'},
  F:  { bg: 'bg-rose-400/20',    text: 'text-rose-300'   },
};

// English full club name → Chinese (for PL title winners only)
const TITLE_CLUB_ZH = {
  'Arsenal': '阿森纳', 'Blackburn Rovers': '布莱克本', 'Chelsea': '切尔西',
  'Leicester City': '莱斯特城', 'Liverpool': '利物浦',
  'Manchester City': '曼城', 'Manchester United': '曼联',
};

// Returns string | string[] — callers must handle both
function formatAchievement(type, detail, language) {
  const joinDot = (str) =>
    (str || '').split(',').map(s => s.trim()).filter(Boolean).join('、');

  if (language === 'zh') {
    switch (type) {
      case '出场250次':
        return `英超出场 ${detail.replace('场', '')} 场`;
      case '单队200场': {
        const [team, apps] = (detail || '').split('|');
        return `为${team}出场 ${apps} 场英超`;
      }
      case '百球':
        return `英超进球 ${detail} 球`;
      case '百大零封':
        return `英超零封 ${detail} 次`;
      case '三冠王': {
        const [seasonsStr, clubsStr] = (detail || '').split('§');
        const seasons = (seasonsStr || '').split(',').map(s => s.trim()).filter(Boolean);
        const clubParts = (clubsStr || '').split(',').map(s => s.trim()).filter(Boolean);
        const seasonsLine = `赛季：${seasons.join('、')}`;
        if (clubParts.length === 0) return [`英超冠军`, seasonsLine];
        const clubLines = clubParts.map(c => {
          const match = c.match(/^(.+?)\s*\((\d+)\)$/);
          if (match) {
            const zhName = TITLE_CLUB_ZH[match[1].trim()] || match[1].trim();
            return `英超冠军 × ${zhName}（${match[2]}次）`;
          }
          return `英超冠军 × ${TITLE_CLUB_ZH[c] || c}`;
        });
        return [...clubLines, seasonsLine];
      }
      case '金靴奖':
        return `英超射手王：${joinDot(detail)}`;
      case '金手套奖':
        return `英超最佳门将：${joinDot(detail)}`;
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
        const [seasonsStr, clubsStr] = (detail || '').split('§');
        const seasons = (seasonsStr || '').split(',').map(s => s.trim()).filter(Boolean);
        const clubParts = (clubsStr || '').split(',').map(s => s.trim()).filter(Boolean);
        const seasonsLine = `Seasons: ${seasons.join(', ')}`;
        if (clubParts.length === 0) return [`PL Champion`, seasonsLine];
        const clubLines = clubParts.map(c => {
          const match = c.match(/^(.+?)\s*\((\d+)\)$/);
          if (match) return `PL Champion × ${match[1].trim()} (${match[2]}×)`;
          return `PL Champion × ${c}`;
        });
        return [...clubLines, seasonsLine];
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

  const pos      = (player.position || '').toUpperCase().charAt(0);
  const posLabel = POSITION_LABEL[pos] || pos;
  const posStyle = POSITION_COLOR[pos] || { bg: 'bg-slate-400/20', text: 'text-slate-300' };

  // Accent colour — 4-way status
  const STATUS_COLOR = {
    hall_of_fame:  '#FFD700',
    active_pl:     '#07c160',
    active_not_pl: '#ff2882',
    retired:       '#475569',
  };
  const accentColor = STATUS_COLOR[player.player_status] || '#475569';

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
            {player.nationality && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/10 text-slate-300 border border-white/20 whitespace-nowrap">
                {nationalityFlag[player.nationality] || ''}{' '}
                {language === 'zh' ? (nationalityZh[player.nationality] || player.nationality) : player.nationality}
              </span>
            )}
            {player.hof_year && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full whitespace-nowrap" style={{ background: '#FFD70022', color: '#FFD700', border: '1px solid #FFD70055' }}>
                {language === 'zh' ? `${player.hof_year}年入选` : `Inducted ${player.hof_year}`}
              </span>
            )}
          </div>
        </div>

        {/* Clubs */}
        {player.clubs && player.clubs.length > 0 && (
          <div className="flex items-start gap-1.5 text-xs text-slate-300">
            <Building className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
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
              {achievements.flatMap((a, i) => {
                const result = formatAchievement(a.type, a.detail, language);
                const lines = Array.isArray(result) ? result : [result];
                return lines.map((line, j) => (
                  <li key={`${i}-${j}`} className="text-xs text-slate-200 leading-relaxed flex gap-1 items-baseline">
                    <span className="text-[#FFD700]/50 shrink-0 select-none">·</span>
                    <span>{line}</span>
                  </li>
                ));
              })}
            </ul>
          </div>
        )}

        {/* Near-miss gaps */}
        {showGap && gapItems.length > 0 && (
          <div className="mt-auto pt-2 border-t border-white/10 flex items-start gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-[#07c160] shrink-0 mt-0.5" />
            <ul className="space-y-0.5 flex-1">
              {gapItems.map((item, i) => (
                <li key={i} className="text-xs text-[#07c160]/90 leading-relaxed flex gap-1 items-baseline">
                  <span className="shrink-0 select-none">·</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
