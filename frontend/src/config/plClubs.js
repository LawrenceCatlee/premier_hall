/**
 * 当赛季英超球队名单
 * 每赛季升降级后在此处更新，前端所有逻辑均引用这个文件
 */

// 中文俱乐部名（展示用）
export const CURRENT_PL_CLUBS_ZH = [
  '曼城', '利物浦', '阿森纳', '切尔西', '热刺', '曼联',
  '狼队', '西汉姆联', '利兹联', '桑德兰', '布莱顿', '维拉',
  '伯恩茅斯', '水晶宫', '伯恩利', '纽卡斯尔', '诺丁汉森林', '布伦特福德', '富勒姆',
];

// 英文俱乐部名（匹配 players.json 中的 current_club 字段）
export const CURRENT_PL_CLUBS_EN = new Set([
  'Manchester City', 'Liverpool', 'Arsenal', 'Chelsea', 'Tottenham Hotspur',
  'Manchester United', 'Wolverhampton Wanderers', 'West Ham United', 'Leeds United',
  'Sunderland', 'Brighton & Hove Albion', 'Aston Villa', 'Bournemouth',
  'Crystal Palace', 'Burnley', 'Newcastle United', 'Nottingham Forest',
  'Brentford', 'Fulham',
]);
