import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Filter } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useLanguage } from '../LanguageContext';
import { translations } from '../translations';

const getAchievementTypes = (t) => [
  { value: 'all', label: t.achievements.all },
  { value: '出场250次', label: t.achievements.appearances250 },
  { value: '单队200场', label: t.achievements.singleClub200 },
  { value: '最佳阵容', label: t.achievements.teamOfYear },
  { value: '金靴奖', label: t.achievements.goldenBoot },
  { value: '金手套奖', label: t.achievements.goldenGlove },
  { value: '年度最佳', label: t.achievements.playerOfYear },
  { value: '三冠王', label: t.achievements.threeChampionships },
  { value: '百球', label: t.achievements.century }
];

const getClubs = (t) => [
  { value: 'all', label: t.clubs.all },
  { value: '曼联', label: t.clubs.manUtd },
  { value: '阿森纳', label: t.clubs.arsenal },
  { value: '切尔西', label: t.clubs.chelsea },
  { value: '利物浦', label: t.clubs.liverpool },
  { value: '曼城', label: t.clubs.manCity },
  { value: '热刺', label: t.clubs.tottenham },
  { value: '埃弗顿', label: t.clubs.everton },
  { value: '纽卡斯尔', label: t.clubs.newcastle },
  { value: '阿斯顿维拉', label: t.clubs.astonVilla },
  { value: '其他', label: t.clubs.other }
];

export default function PlayerFilters({ 
  selectedClub, 
  selectedAchievement,
  selectedStatus,
  selectedPlayerStatus,
  onClubChange, 
  onAchievementChange,
  onStatusChange,
  onPlayerStatusChange,
  onClear 
}) {
  const { language } = useLanguage();
  const t = translations[language];
  const ACHIEVEMENT_TYPES = getAchievementTypes(t);
  const CLUBS = getClubs(t);

  const hasFilters = selectedClub !== 'all' || selectedAchievement !== 'all' || selectedStatus !== 'all' || selectedPlayerStatus !== 'all';

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Filter className="w-5 h-5 text-[#37003c]" />
        <h3 className="text-lg font-semibold text-slate-900">{t.filters}</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="text-sm font-medium text-slate-700 mb-2 block">
            {t.club}
          </label>
          <Select value={selectedClub} onValueChange={onClubChange}>
            <SelectTrigger>
              <SelectValue placeholder={t.club} />
            </SelectTrigger>
            <SelectContent>
              {CLUBS.map(club => (
                <SelectItem key={club.value} value={club.value}>
                  {club.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-2 block">
            {t.achievement}
          </label>
          <Select value={selectedAchievement} onValueChange={onAchievementChange}>
            <SelectTrigger>
              <SelectValue placeholder={t.achievement} />
            </SelectTrigger>
            <SelectContent>
              {ACHIEVEMENT_TYPES.map(type => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-2 block">
            {t.qualificationStatus}
          </label>
          <Select value={selectedStatus} onValueChange={onStatusChange}>
            <SelectTrigger>
              <SelectValue placeholder={t.qualificationStatus} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t.allStatus}</SelectItem>
              <SelectItem value="qualified">{t.qualified}</SelectItem>
              <SelectItem value="near_miss">{t.nearMiss}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700 mb-2 block">
            {t.playerStatus}
          </label>
          <Select value={selectedPlayerStatus} onValueChange={onPlayerStatusChange}>
            <SelectTrigger>
              <SelectValue placeholder={t.playerStatus} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t.allPlayers}</SelectItem>
              <SelectItem value="active">{t.active}</SelectItem>
              <SelectItem value="retired">{t.retired}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {hasFilters && (
        <div className="mt-4 flex items-center gap-2 flex-wrap">
          <span className="text-sm text-slate-600">{t.currentFilters}</span>
          {selectedClub !== 'all' && (
            <Badge variant="secondary">
              {CLUBS.find(c => c.value === selectedClub)?.label}
            </Badge>
          )}
          {selectedAchievement !== 'all' && (
            <Badge variant="secondary">
              {ACHIEVEMENT_TYPES.find(a => a.value === selectedAchievement)?.label}
            </Badge>
          )}
          {selectedStatus !== 'all' && (
            <Badge variant="secondary">
              {selectedStatus === 'qualified' ? t.qualified : t.nearMiss}
            </Badge>
          )}
          {selectedPlayerStatus !== 'all' && (
            <Badge variant="secondary">
              {selectedPlayerStatus === 'active' ? t.active : t.retired}
            </Badge>
          )}
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onClear}
            className="ml-auto"
          >
            <X className="w-4 h-4 mr-1" />
            {t.clearFilters}
          </Button>
        </div>
      )}
    </div>
  );
}