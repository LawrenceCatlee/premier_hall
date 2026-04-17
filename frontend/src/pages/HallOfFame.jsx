import { useState, useMemo } from 'react';
import { useQuery } from "@tanstack/react-query";
import { fetchPlayers } from "@/api/playersApi";
import { Trophy, Search } from 'lucide-react';
import PlayerCard from '../components/players/PlayerCard';
import PlayerFilters from '../components/players/PlayerFilters';
import LanguageToggle from '../components/LanguageToggle';
import { useLanguage } from '../components/LanguageContext';
import { translations } from '../components/translations';

export default function HallOfFame() {
  const { language } = useLanguage();
  const t = translations[language];

  const [selectedClub, setSelectedClub] = useState('all');
  const [selectedAchievement, setSelectedAchievement] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedPlayerStatus, setSelectedPlayerStatus] = useState('all');
  const [selectedNationality, setSelectedNationality] = useState('all');
  const [searchName, setSearchName] = useState('');

  const { data: players = [], isLoading } = useQuery({
    queryKey: ['players'],
    queryFn: fetchPlayers,
  });

  // Helper: get achievement type strings from either old string[] or new {type,detail}[]
  const getAchievementTypes = (achievements) =>
    (achievements || []).map(a => (typeof a === 'string' ? a : a.type));

  // Build gap_items for near-miss players — each item is a descriptive string
  const buildGapItems = (player, lang) => {
    const items = [];
    const zh = lang === 'zh';

    if (player.total_appearances >= 230 && player.total_appearances < 250) {
      const diff = 250 - player.total_appearances;
      items.push(zh
        ? `距英超出场250次：已有${player.total_appearances}场，还差${diff}场`
        : `250 PL Appearances: ${player.total_appearances} now, ${diff} to go`);
    }
    if (player.single_club_appearances != null &&
        player.single_club_appearances >= 180 &&
        player.single_club_appearances < 200) {
      const diff = Math.ceil(200 - player.single_club_appearances);
      const club = player.single_club_name || '';
      items.push(zh
        ? `距单队200场（${club || '当前队'}）：已有${player.single_club_appearances}场，还差${diff}场`
        : `Single Club 200 (${club || '?'}): ${player.single_club_appearances} now, ${diff} to go`);
    }
    if (player.goals != null && player.goals > 80 && player.goals < 100) {
      const diff = 100 - player.goals;
      items.push(zh
        ? `距百球：已有${player.goals}球，还差${diff}球`
        : `100 Goals: ${player.goals} now, ${diff} to go`);
    }
    if (player.clean_sheets != null && player.clean_sheets > 80 && player.clean_sheets < 100) {
      const diff = 100 - player.clean_sheets;
      items.push(zh
        ? `距百大零封：已有${player.clean_sheets}次，还差${diff}次`
        : `100 Clean Sheets: ${player.clean_sheets} now, ${diff} to go`);
    }
    return items;
  };

  const qualifiedPlayers = useMemo(() => {
    return players.filter(p => p.achievements && p.achievements.length > 0);
  }, [players]);

  // Near-miss: only active_pl players without achievements who are approaching a milestone
  const nearMissPlayers = useMemo(() => {
    return players
      .filter(player => {
        if (player.achievements && player.achievements.length > 0) return false;
        if (player.player_status !== 'active_pl') return false;
        return (
          (player.total_appearances >= 230 && player.total_appearances < 250) ||
          (player.single_club_appearances != null &&
            player.single_club_appearances >= 180 &&
            player.single_club_appearances < 200) ||
          (player.goals != null && player.goals > 80 && player.goals < 100) ||
          (player.clean_sheets != null && player.clean_sheets > 80 && player.clean_sheets < 100)
        );
      })
      .map(player => ({
        ...player,
        gap_items: buildGapItems(player, language),
      }));
  }, [players, language]);

  const allPlayers = useMemo(() => [...qualifiedPlayers, ...nearMissPlayers], [qualifiedPlayers, nearMissPlayers]);

  // Sorted unique nationality list for filter dropdown
  const nationalities = useMemo(() => {
    const set = new Set(allPlayers.map(p => p.nationality).filter(Boolean));
    return Array.from(set).sort();
  }, [allPlayers]);

  const filteredPlayers = useMemo(() => {
    let filtered = allPlayers;

    // 姓名搜索（中英文均可）
    const q = searchName.trim().toLowerCase();
    if (q) {
      filtered = filtered.filter(p =>
        (p.name_en || '').toLowerCase().includes(q) ||
        (p.name_cn || '').toLowerCase().includes(q)
      );
    }

    if (selectedStatus === 'qualified') {
      filtered = filtered.filter(p => p.achievements && p.achievements.length > 0);
    } else if (selectedStatus === 'near_miss') {
      filtered = filtered.filter(p => !p.achievements || p.achievements.length === 0);
    } else if (selectedStatus === 'hall_of_fame') {
      filtered = filtered.filter(p => p.player_status === 'hall_of_fame');
    }

    if (selectedPlayerStatus !== 'all') {
      filtered = filtered.filter(p => p.player_status === selectedPlayerStatus);
    }

    if (selectedNationality !== 'all') {
      filtered = filtered.filter(p => p.nationality === selectedNationality);
    }

    if (selectedClub !== 'all') {
      filtered = filtered.filter(p => p.clubs?.some(c => c.includes(selectedClub)));
    }

    if (selectedAchievement !== 'all') {
      const nearMissCheck = {
        '出场250次':  p => p.total_appearances >= 230 && p.total_appearances < 250,
        '单队200场':  p => p.single_club_appearances != null && p.single_club_appearances >= 180 && p.single_club_appearances < 200,
        '百球':       p => p.goals != null && p.goals > 80 && p.goals < 100,
        '百大零封':   p => p.clean_sheets != null && p.clean_sheets > 80 && p.clean_sheets < 100,
      };
      filtered = filtered.filter(p => {
        if (getAchievementTypes(p.achievements).some(type => type.includes(selectedAchievement))) return true;
        const check = nearMissCheck[selectedAchievement];
        return check ? check(p) : false;
      });
    }

    return filtered;
  }, [allPlayers, searchName, selectedClub, selectedAchievement, selectedStatus, selectedPlayerStatus, selectedNationality]);

  const stats = useMemo(() => ({
    qualified: qualifiedPlayers.length,
    nearMiss: nearMissPlayers.length,
    inducted: allPlayers.filter(p => p.player_status === 'hall_of_fame').length,
    activePL: allPlayers.filter(p => p.player_status === 'active_pl').length,
    activeNotPL: allPlayers.filter(p => p.player_status === 'active_not_pl').length,
  }), [qualifiedPlayers, nearMissPlayers, allPlayers]);

  const handleClearFilters = () => {
    setSelectedClub('all');
    setSelectedAchievement('all');
    setSelectedStatus('all');
    setSelectedPlayerStatus('all');
    setSelectedNationality('all');
    setSearchName('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a0020] via-[#2d0036] to-[#1a0020]">
      {/* Hero */}
      <div className="relative overflow-hidden py-14 px-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_#4a0e4e_0%,_transparent_70%)] pointer-events-none" />
        <div className="relative max-w-7xl mx-auto">
          <div className="absolute top-0 right-0">
            <LanguageToggle />
          </div>

          <div className="flex items-center justify-center gap-3 mb-2">
            <Trophy className="w-10 h-10 text-[#FFD700]" />
            <h1 className="text-5xl font-extrabold tracking-tight text-white">
              {t.title}
            </h1>
          </div>
          <p className="text-center text-base text-slate-300 mb-10">{t.subtitle}</p>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 max-w-4xl mx-auto">
            {[
              { value: stats.qualified,   label: t.qualified,           accent: '#00ff85' },
              { value: stats.nearMiss,    label: t.nearMiss,            accent: '#ff2882' },
              { value: stats.inducted,    label: t.hallOfFame,          accent: '#FFD700' },
              { value: stats.activePL,    label: t.statusActivePL,      accent: '#07c160' },
              { value: stats.activeNotPL, label: t.statusActiveNotPL,   accent: '#f59e0b' },
            ].map(({ value, label, accent }) => (
              <div
                key={label}
                className="rounded-xl p-4 text-center"
                style={{ background: `${accent}18`, border: `1px solid ${accent}55` }}
              >
                <p className="text-3xl font-bold mb-0.5" style={{ color: accent }}>{value}</p>
                <p className="text-xs text-slate-300">{label}</p>
              </div>
            ))}
          </div>

          {/* Color legend */}
          <div className="mt-6 flex items-center justify-center gap-5 flex-wrap">
            <span className="text-xs text-slate-500 mr-1">{t.legendTitle}:</span>
            {[
              { color: '#FFD700', label: t.legendHoF },
              { color: '#07c160', label: t.legendActive },
              { color: '#ff2882', label: t.legendActiveNotPL },
              { color: '#475569', label: t.legendRetired },
            ].map(({ color, label }) => (
              <span key={label} className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                {label}
              </span>
            ))}
          </div>

          {/* Search bar */}
          <div className="mt-6 max-w-md mx-auto">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchName}
                onChange={e => setSearchName(e.target.value)}
                placeholder={language === 'zh' ? '搜索球员姓名…' : 'Search player name…'}
                className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-white/10 border border-white/20 text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFD700]/60"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-6 pb-12">
        <PlayerFilters
          selectedClub={selectedClub}
          selectedAchievement={selectedAchievement}
          selectedStatus={selectedStatus}
          selectedPlayerStatus={selectedPlayerStatus}
          selectedNationality={selectedNationality}
          nationalities={nationalities}
          onClubChange={setSelectedClub}
          onAchievementChange={setSelectedAchievement}
          onStatusChange={setSelectedStatus}
          onPlayerStatusChange={setSelectedPlayerStatus}
          onNationalityChange={setSelectedNationality}
          onClear={handleClearFilters}
        />

        {isLoading ? (
          <div className="text-center py-20">
            <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-[#FFD700] border-r-transparent" />
            <p className="mt-4 text-slate-400">{t.loading}</p>
          </div>
        ) : filteredPlayers.length === 0 ? (
          <div className="text-center py-20">
            <Trophy className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <p className="text-xl text-slate-400">
              {players.length === 0 ? t.noData : t.noMatch}
            </p>
          </div>
        ) : (
          <>
            <div className="mb-5 text-sm text-slate-400">
              {t.showing}{' '}
              <span className="font-semibold text-white">{filteredPlayers.length}</span>{' '}
              {t.players}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {filteredPlayers.map(player => (
                <PlayerCard
                  key={player.id}
                  player={player}
                  showGap={!player.achievements || player.achievements.length === 0}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
