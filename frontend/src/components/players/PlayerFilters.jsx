import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Filter } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useLanguage } from '../LanguageContext';
import { translations, nationalityFlag, nationalityZh, clubNameMap } from '../translations';

const getAchievementTypes = (t) => [
  { value: 'all', label: t.achievements.all },
  { value: '出场250次', label: t.achievements.appearances250 },
  { value: '单队200场', label: t.achievements.singleClub200 },
  { value: '百球', label: t.achievements.century100goals },
  { value: '百大零封', label: t.achievements.century100clean },
  { value: '三冠王', label: t.achievements.threeChampionships },
  { value: '金靴奖', label: t.achievements.goldenBoot },
  { value: '金手套奖', label: t.achievements.goldenGlove },
  { value: '年度最佳', label: t.achievements.playerOfYear },
  { value: '最佳阵容', label: t.achievements.teamOfYear },
];


export default function PlayerFilters({
  selectedClub,
  selectedAchievement,
  selectedStatus,
  selectedPlayerStatus,
  selectedNationality,
  nationalities = [],
  clubs = [],
  onClubChange,
  onAchievementChange,
  onStatusChange,
  onPlayerStatusChange,
  onNationalityChange,
  onClear,
}) {
  const { language } = useLanguage();
  const t = translations[language];
  const ACHIEVEMENT_TYPES = getAchievementTypes(t);
  const CLUB_OPTIONS = [
    { value: 'all', label: t.allClubs },
    ...clubs.map(c => ({
      value: c,
      label: language === 'zh' ? c : (clubNameMap[c] || c),
    })),
  ];

  const hasFilters =
    selectedClub !== 'all' ||
    selectedAchievement !== 'all' ||
    selectedStatus !== 'all' ||
    selectedPlayerStatus !== 'all' ||
    selectedNationality !== 'all';

  const NAT_OPTIONS = [
    { value: 'all', label: t.allNationalities },
    ...nationalities.map((n) => ({
      value: n,
      label: `${nationalityFlag[n] || ''} ${language === 'zh' ? (nationalityZh[n] || n) : n}`.trim(),
    })),
  ];

  const triggerCls = "bg-white/10 border-white/20 text-white";

  return (
    <div className="rounded-xl p-4 mb-6 bg-white/5 backdrop-blur-sm border border-white/10">
      <div className="flex items-center gap-2 mb-4">
        <Filter className="w-5 h-5 text-slate-400" />
        <h3 className="text-lg font-semibold text-white">{t.filters}</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {/* Club */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wide">
            {t.club}
          </label>
          <Select value={selectedClub} onValueChange={onClubChange}>
            <SelectTrigger className={triggerCls}>
              <SelectValue placeholder={t.club} />
            </SelectTrigger>
            <SelectContent>
              {CLUB_OPTIONS.map(club => (
                <SelectItem key={club.value} value={club.value}>{club.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Achievement */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wide">
            {t.achievement}
          </label>
          <Select value={selectedAchievement} onValueChange={onAchievementChange}>
            <SelectTrigger className={triggerCls}>
              <SelectValue placeholder={t.achievement} />
            </SelectTrigger>
            <SelectContent>
              {ACHIEVEMENT_TYPES.map(type => (
                <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Qualification status */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wide">
            {t.qualificationStatus}
          </label>
          <Select value={selectedStatus} onValueChange={onStatusChange}>
            <SelectTrigger className={triggerCls}>
              <SelectValue placeholder={t.qualificationStatus} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t.allStatus}</SelectItem>
              <SelectItem value="qualified">{t.qualified}</SelectItem>
              <SelectItem value="near_miss">{t.nearMiss}</SelectItem>
              <SelectItem value="hall_of_fame">{t.inducted}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Player status */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wide">
            {t.playerStatus}
          </label>
          <Select value={selectedPlayerStatus} onValueChange={onPlayerStatusChange}>
            <SelectTrigger className={triggerCls}>
              <SelectValue placeholder={t.playerStatus} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t.allPlayers}</SelectItem>
              <SelectItem value="active_pl">{t.statusActivePL}</SelectItem>
              <SelectItem value="active_not_pl">{t.statusActiveNotPL}</SelectItem>
              <SelectItem value="retired">{t.statusRetired}</SelectItem>
              <SelectItem value="hall_of_fame">{t.statusHoF}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Nationality */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wide">
            {t.nationality}
          </label>
          <Select value={selectedNationality} onValueChange={onNationalityChange}>
            <SelectTrigger className={triggerCls}>
              <SelectValue placeholder={t.allNationalities} />
            </SelectTrigger>
            <SelectContent>
              {NAT_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {hasFilters && (
        <div className="mt-4 flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400">{t.currentFilters}</span>
          {selectedClub !== 'all' && (
            <Badge variant="secondary" className="bg-white/10 text-slate-200 border-white/20">
              {CLUB_OPTIONS.find(c => c.value === selectedClub)?.label}
            </Badge>
          )}
          {selectedAchievement !== 'all' && (
            <Badge variant="secondary" className="bg-white/10 text-slate-200 border-white/20">
              {ACHIEVEMENT_TYPES.find(a => a.value === selectedAchievement)?.label}
            </Badge>
          )}
          {selectedStatus !== 'all' && (
            <Badge variant="secondary" className="bg-white/10 text-slate-200 border-white/20">
              {{ qualified: t.qualified, near_miss: t.nearMiss, hall_of_fame: t.inducted }[selectedStatus] || selectedStatus}
            </Badge>
          )}
          {selectedPlayerStatus !== 'all' && (
            <Badge variant="secondary" className="bg-white/10 text-slate-200 border-white/20">
              {t[{active_pl:'statusActivePL',active_not_pl:'statusActiveNotPL',retired:'statusRetired',hall_of_fame:'statusHoF'}[selectedPlayerStatus]] || selectedPlayerStatus}
            </Badge>
          )}
          {selectedNationality !== 'all' && (
            <Badge variant="secondary" className="bg-white/10 text-slate-200 border-white/20">
              {nationalityFlag[selectedNationality] || ''}{' '}
              {language === 'zh' ? (nationalityZh[selectedNationality] || selectedNationality) : selectedNationality}
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onClear}
            className="ml-auto text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4 mr-1" />
            {t.clearFilters}
          </Button>
        </div>
      )}
    </div>
  );
}
