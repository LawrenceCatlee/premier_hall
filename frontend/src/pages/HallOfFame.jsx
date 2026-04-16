import React, { useState, useMemo } from 'react';
import { useQuery } from "@tanstack/react-query";
import { fetchPlayers } from "@/api/playersApi";
import { Trophy } from 'lucide-react';
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

  const { data: players = [], isLoading } = useQuery({
    queryKey: ['players'],
    queryFn: fetchPlayers,
  });

  // Helper: get achievement type string (supports both old string[] and new {type,detail}[])
  const getAchievementTypes = (achievements) =>
    (achievements || []).map(a => (typeof a === 'string' ? a : a.type));

  const qualifiedPlayers = useMemo(() => {
    return players.filter(player => player.achievements && player.achievements.length > 0);
  }, [players]);

  const nearMissPlayers = useMemo(() => {
    return players
      .filter(player => {
        if (player.achievements && player.achievements.length > 0) {
          return false;
        }

        const hasNearMiss =
          (player.total_appearances >= 230 && player.total_appearances < 250) ||
          (player.single_club_appearances != null && player.single_club_appearances >= 180 && player.single_club_appearances < 200) ||
          (player.goals >= 80 && player.goals < 100) ||
          (player.clean_sheets >= 80 && player.clean_sheets < 100);

        return hasNearMiss;
      })
      .map(player => {
        const gaps = [];

        if (player.total_appearances >= 230 && player.total_appearances < 250) {
          gaps.push(`还差${250 - player.total_appearances}场出场`);
        }
        if (player.single_club_appearances != null && player.single_club_appearances >= 180 && player.single_club_appearances < 200) {
          gaps.push(`单队还差${Math.ceil(200 - player.single_club_appearances)}场`);
        }
        if (player.goals >= 80 && player.goals < 100) {
          gaps.push(`还差${100 - player.goals}个进球`);
        }
        if (player.clean_sheets >= 80 && player.clean_sheets < 100) {
          gaps.push(`还差${100 - player.clean_sheets}场零封`);
        }

        return {
          ...player,
          gap_info: gaps.join('，')
        };
      });
  }, [players]);

  const allPlayers = useMemo(() => {
    return [...qualifiedPlayers, ...nearMissPlayers];
  }, [qualifiedPlayers, nearMissPlayers]);

  const filteredPlayers = useMemo(() => {
    let filtered = allPlayers;

    // 资格状态筛选
    if (selectedStatus === 'qualified') {
      filtered = filtered.filter(player => player.achievements && player.achievements.length > 0);
    } else if (selectedStatus === 'near_miss') {
      filtered = filtered.filter(player => !player.achievements || player.achievements.length === 0);
    }

    // 球员状态筛选
    if (selectedPlayerStatus === 'active') {
      filtered = filtered.filter(player => player.is_active);
    } else if (selectedPlayerStatus === 'retired') {
      filtered = filtered.filter(player => !player.is_active);
    }

    if (selectedClub !== 'all') {
      filtered = filtered.filter(player => 
        player.clubs?.some(club => club.includes(selectedClub))
      );
    }

    if (selectedAchievement !== 'all') {
      filtered = filtered.filter(player =>
        getAchievementTypes(player.achievements).some(type =>
          type.includes(selectedAchievement)
        )
      );
    }

    return filtered;
  }, [allPlayers, selectedClub, selectedAchievement, selectedStatus, selectedPlayerStatus]);

  const stats = useMemo(() => {
    return {
      qualified: qualifiedPlayers.length,
      nearMiss: nearMissPlayers.length,
      inducted: qualifiedPlayers.filter(p => p.is_hall_of_fame).length,
      active: allPlayers.filter(p => p.is_active).length,
      retired: allPlayers.filter(p => !p.is_active).length
    };
  }, [qualifiedPlayers, nearMissPlayers, allPlayers]);

  const handleClearFilters = () => {
    setSelectedClub('all');
    setSelectedAchievement('all');
    setSelectedStatus('all');
    setSelectedPlayerStatus('all');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      {/* Hero Section */}
      <div className="bg-gradient-to-r from-[#37003c] via-[#4a0e4e] to-[#37003c] text-white py-16 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="absolute top-6 right-6">
            <LanguageToggle />
          </div>
          
          <div className="flex items-center justify-center gap-3 mb-4">
            <Trophy className="w-12 h-12 text-[#00ff85]" />
            <h1 className="text-5xl font-bold">{t.title}</h1>
          </div>
          <p className="text-center text-xl text-slate-200 mb-8">
            {t.subtitle}
          </p>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 max-w-5xl mx-auto">
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 text-center border border-white/20">
              <p className="text-3xl font-bold mb-1 text-[#00ff85]">{stats.qualified}</p>
              <p className="text-sm text-slate-200">{t.qualified}</p>
            </div>
            <div className="bg-[#ff2882]/20 backdrop-blur-sm rounded-lg p-4 text-center border-2 border-[#ff2882]">
              <p className="text-3xl font-bold mb-1">{stats.nearMiss}</p>
              <p className="text-sm text-slate-200">{t.nearMiss}</p>
            </div>
            <div className="bg-[#00ff85]/20 backdrop-blur-sm rounded-lg p-4 text-center border-2 border-[#00ff85]">
              <p className="text-3xl font-bold mb-1">{stats.inducted}</p>
              <p className="text-sm text-slate-200">{t.hallOfFame}</p>
            </div>
            <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4 text-center border-2 border-white">
              <p className="text-3xl font-bold mb-1">{stats.active}</p>
              <p className="text-sm text-slate-200">{t.active}</p>
            </div>
            <div className="bg-slate-700/30 backdrop-blur-sm rounded-lg p-4 text-center border-2 border-slate-400">
              <p className="text-3xl font-bold mb-1">{stats.retired}</p>
              <p className="text-sm text-slate-200">{t.retired}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-10">
        <PlayerFilters
          selectedClub={selectedClub}
          selectedAchievement={selectedAchievement}
          selectedStatus={selectedStatus}
          selectedPlayerStatus={selectedPlayerStatus}
          onClubChange={setSelectedClub}
          onAchievementChange={setSelectedAchievement}
          onStatusChange={setSelectedStatus}
          onPlayerStatusChange={setSelectedPlayerStatus}
          onClear={handleClearFilters}
        />

        {isLoading ? (
          <div className="text-center py-20">
            <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-[#37003c] border-r-transparent"></div>
            <p className="mt-4 text-slate-600">{t.loading}</p>
          </div>
        ) : filteredPlayers.length === 0 ? (
          <div className="text-center py-20">
            <Trophy className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-xl text-slate-600">
              {players.length === 0 ? t.noData : t.noMatch}
            </p>
          </div>
        ) : (
          <>
            <div className="mb-6 text-slate-600">
              {t.showing} <span className="font-semibold text-[#37003c]">{filteredPlayers.length}</span> {t.players}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
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