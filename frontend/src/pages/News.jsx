import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchNewsArchive } from '@/api/newsApi';
import { useLanguage } from '../components/LanguageContext';
import { Newspaper, ExternalLink, Clock, Search } from 'lucide-react';

const TIER_DOT   = { 3: '#ef4444', 2: '#eab308', 1: '#94a3b8' };
const TIER_LABEL = { 3: '独家快讯', 2: '英超媒体', 1: '综合体育' };
const SOURCES    = ['全部', 'BBC Sport', 'Sky Sports', 'The Guardian', 'ESPN FC', 'Goal.com', 'Transfermarkt', '罗马诺'];

function timeAgo(isoStr, lang) {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 60000);
  if (lang === 'zh') {
    if (diff < 60)   return `${diff}分钟前`;
    if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
    return `${Math.floor(diff / 1440)}天前`;
  }
  if (diff < 60)   return `${diff}m ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
  return `${Math.floor(diff / 1440)}d ago`;
}

function NewsItem({ item, lang }) {
  const [expanded, setExpanded] = useState(false);
  const hasCn = item.title_cn || item.summary_cn;

  return (
    <div
      className="rounded-xl p-4 transition-colors hover:bg-white/5 cursor-pointer"
      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}
      onClick={() => hasCn && setExpanded(v => !v)}
    >
      <div className="flex gap-3 items-start">
        {/* Tier dot */}
        <span
          className="mt-1.5 shrink-0 w-2.5 h-2.5 rounded-full"
          style={{ background: TIER_DOT[item.tier] ?? '#94a3b8' }}
          title={TIER_LABEL[item.tier]}
        />

        <div className="min-w-0 flex-1">
          {/* Chinese title */}
          {item.title_cn && (
            <p className="text-white font-semibold text-base leading-snug mb-1">
              {item.title_cn}
            </p>
          )}

          {/* English title with link */}
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="flex items-start gap-1 text-sm text-slate-400 hover:text-slate-200 leading-snug group"
          >
            <span className="flex-1">{item.title}</span>
            <ExternalLink className="w-3 h-3 shrink-0 mt-0.5 opacity-0 group-hover:opacity-100" />
          </a>

          {/* Chinese summary (expandable) */}
          {item.summary_cn && expanded && (
            <p className="mt-2 text-sm text-slate-300 leading-relaxed border-l-2 border-[#FFD700]/40 pl-3">
              {item.summary_cn}
            </p>
          )}

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-2">
            <span
              className="text-[11px] px-2 py-0.5 rounded-full"
              style={{ background: `${TIER_DOT[item.tier]}22`, color: TIER_DOT[item.tier] }}
            >
              {item.source}
            </span>
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Clock className="w-3 h-3" />
              {timeAgo(item.published || item.fetched_at, lang)}
            </span>
            {item.keywords?.slice(0, 3).map(kw => (
              <span
                key={kw}
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: 'rgba(255,215,0,0.08)', color: '#FFD70099' }}
              >
                {kw}
              </span>
            ))}
            {item.summary_cn && (
              <button
                onClick={e => { e.stopPropagation(); setExpanded(v => !v); }}
                className="text-[10px] text-slate-500 hover:text-slate-300 ml-auto"
              >
                {expanded ? '收起' : '查看摘要'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function News() {
  const { language } = useLanguage();
  const [search, setSearch]     = useState('');
  const [source, setSource]     = useState('全部');
  const [page, setPage]         = useState(1);
  const PAGE_SIZE = 30;

  const { data, isLoading } = useQuery({
    queryKey: ['newsArchive'],
    queryFn: fetchNewsArchive,
    staleTime: 1000 * 60 * 5,
  });

  const items = data?.items ?? [];

  const filtered = useMemo(() => {
    let list = items;
    if (source !== '全部') list = list.filter(i => i.source === source);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(i =>
        i.title?.toLowerCase().includes(q) ||
        i.title_cn?.includes(q) ||
        i.summary_cn?.includes(q) ||
        i.keywords?.some(k => k.toLowerCase().includes(q))
      );
    }
    return list;
  }, [items, source, search]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSearch = (v) => { setSearch(v); setPage(1); };
  const handleSource = (v) => { setSource(v); setPage(1); };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a0020] via-[#2d0036] to-[#1a0020]">
      {/* Header */}
      <div className="relative overflow-hidden py-8 sm:py-12 px-4 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_#4a0e4e_0%,_transparent_70%)] pointer-events-none" />
        <div className="relative max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <Newspaper className="w-7 h-7 text-[#FFD700]" />
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
              {language === 'zh' ? '新闻快报' : 'Sports News'}
            </h1>
            <span className="text-sm text-slate-400 ml-1">
              {language === 'zh' ? `共 ${items.length} 条` : `${items.length} articles`}
            </span>
          </div>
          <p className="text-slate-400 text-sm mb-6">
            {language === 'zh' ? '每小时自动更新 · 点击条目可查看中文摘要' : 'Auto-updated hourly · Click to expand summary'}
          </p>

          {/* Search + Source filter */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={e => handleSearch(e.target.value)}
                placeholder={language === 'zh' ? '搜索标题、关键词…' : 'Search…'}
                className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-white/10 border border-white/20 text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFD700]/60"
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              {SOURCES.map(s => (
                <button
                  key={s}
                  onClick={() => handleSource(s)}
                  className="text-xs px-3 py-2 rounded-lg transition-colors"
                  style={source === s
                    ? { background: '#FFD700', color: '#1a0020', fontWeight: 600 }
                    : { background: 'rgba(255,255,255,0.08)', color: '#94a3b8' }
                  }
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* News list */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-12">
        {isLoading ? (
          <div className="text-center py-20">
            <div className="inline-block h-10 w-10 animate-spin rounded-full border-4 border-solid border-[#FFD700] border-r-transparent" />
            <p className="mt-4 text-slate-400">{language === 'zh' ? '加载中…' : 'Loading…'}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            {language === 'zh' ? '暂无内容' : 'No results'}
          </div>
        ) : (
          <>
            <p className="text-xs text-slate-500 mb-4">
              {language === 'zh'
                ? `显示第 ${(page-1)*PAGE_SIZE+1}–${Math.min(page*PAGE_SIZE, filtered.length)} 条，共 ${filtered.length} 条`
                : `Showing ${(page-1)*PAGE_SIZE+1}–${Math.min(page*PAGE_SIZE, filtered.length)} of ${filtered.length}`}
            </p>
            <div className="flex flex-col gap-2">
              {paged.map((item, i) => (
                <NewsItem key={item.url + i} item={item} lang={language} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 rounded-lg text-sm disabled:opacity-30 text-slate-300 hover:text-white"
                  style={{ background: 'rgba(255,255,255,0.08)' }}
                >
                  ←
                </button>
                <span className="text-sm text-slate-400">{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 rounded-lg text-sm disabled:opacity-30 text-slate-300 hover:text-white"
                  style={{ background: 'rgba(255,255,255,0.08)' }}
                >
                  →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
