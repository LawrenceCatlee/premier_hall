import { Building, Star, TrendingUp } from 'lucide-react';
import { cn } from "@/lib/utils";
import { useLanguage } from '../LanguageContext';
import { clubNameMap, clubEnToZh, nationalityFlag, nationalityZh } from '../translations';

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
        return `为${clubEnToZh[team] || team}出场 ${apps} 场英超`;
      }
      case '百球':
        return `英超进球 ${detail} 球`;
      case '百大零封':
        return `英超零封 ${detail} 次`;
      case '三冠王': {
        const [seasonsStr, clubsStr] = (detail || '').split('§');
        const seasons = (seasonsStr || '').split(',').map(s => s.trim().replace('–', '-')).filter(Boolean);
        const clubParts = (clubsStr || '').trim()
          ? (clubsStr || '').split(',').map(s => s.trim()).filter(Boolean)
          : [];
        const parsed = clubParts.map(c => {
          const m = c.match(/^(.+?)\s*\((\d+)\)$/);
          return m ? { name: m[1].trim(), count: parseInt(m[2]) } : { name: c, count: seasons.length };
        });
        if (parsed.length === 0) parsed.push({ name: '', count: seasons.length });
        let idx = 0;
        const sublines = parsed.map(({ name, count }) => {
          const s = seasons.slice(idx, idx + count);
          idx += count;
          const zhName = name ? (clubEnToZh[name] || name) : '英超冠军';
          return `${zhName}：${s.join('、')}`;
        });
        return { header: '英超冠军：', sublines };
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
      case '10年最佳阵容':
        return '入选英超10周年最佳阵容';
      case '20年最佳阵容':
        return '入选英超20周年最佳阵容';
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
        const seasons = (seasonsStr || '').split(',').map(s => s.trim().replace('–', '-')).filter(Boolean);
        const clubParts = (clubsStr || '').trim()
          ? (clubsStr || '').split(',').map(s => s.trim()).filter(Boolean)
          : [];
        const parsed = clubParts.map(c => {
          const m = c.match(/^(.+?)\s*\((\d+)\)$/);
          return m ? { name: m[1].trim(), count: parseInt(m[2]) } : { name: c, count: seasons.length };
        });
        if (parsed.length === 0) parsed.push({ name: 'PL Champion', count: seasons.length });
        let idx = 0;
        const sublines = parsed.map(({ name, count }) => {
          const s = seasons.slice(idx, idx + count);
          idx += count;
          return `${name}: ${s.join(', ')}`;
        });
        return { header: 'PL Champion:', sublines };
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
      case '10年最佳阵容':
        return 'PL 10th Season Team XI';
      case '20年最佳阵容':
        return 'PL 20th Season Team XI';
      default:
        return detail ? `${type}: ${detail}` : type;
    }
  }
}

export default function PlayerCard({ player, showGap = false }) {
  const { language } = useLanguage();

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
            <span className="leading-relaxed">
              {language === 'en'
                ? player.clubs.flatMap(c => c.split(';').map(s => s.trim())).filter(Boolean).map(c => clubNameMap[c] || c).join(' · ')
                : player.clubs.flatMap(c => c.split(';').map(s => s.trim())).filter(Boolean).map(c => clubEnToZh[c] || c).join(' · ')}
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
                if (result && typeof result === 'object' && !Array.isArray(result) && result.header) {
                  return [
                    <li key={`${i}-h`} className="text-xs text-slate-200 leading-relaxed flex gap-1 items-baseline">
                      <span className="text-[#FFD700]/50 shrink-0 select-none">·</span>
                      <span>{result.header}</span>
                    </li>,
                    ...result.sublines.map((line, j) => (
                      <li key={`${i}-${j}`} className="text-xs text-slate-300 leading-relaxed pl-4">
                        {line}
                      </li>
                    )),
                  ];
                }
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
