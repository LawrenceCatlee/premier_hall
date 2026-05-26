import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchNews } from '@/api/newsApi';
import { Newspaper, ChevronDown, ChevronUp, ExternalLink, Clock } from 'lucide-react';

const TIER_DOT = { 3: '#ef4444', 2: '#eab308', 1: '#94a3b8' };
const TIER_LABEL_ZH = { 3: '独家', 2: '英超', 1: '体育' };
const TIER_LABEL_EN = { 3: 'Breaking', 2: 'PL', 1: 'Sport' };

function timeAgo(isoStr, lang) {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 60000);
  if (lang === 'zh') {
    if (diff < 60) return `${diff}分钟前`;
    if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
    return `${Math.floor(diff / 1440)}天前`;
  }
  if (diff < 60) return `${diff}m ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
  return `${Math.floor(diff / 1440)}d ago`;
}

export default function NewsPanel({ language = 'zh' }) {
  const [open, setOpen] = useState(true);
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['news'],
    queryFn: fetchNews,
    staleTime: 1000 * 60 * 10,   // 10 分钟内不重新请求
    retry: 1,
  });

  if (isError) return null;

  const items = data?.items ?? [];
  const updatedAt = data?.updated_at;
  const visible = showAll ? items : items.slice(0, 8);

  return (
    <div
      className="rounded-2xl overflow-hidden mb-6"
      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)' }}
    >
      {/* Header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-[#FFD700]" />
          <span className="text-sm font-semibold text-white">
            {language === 'zh' ? '新闻快报' : 'Sports News'}
          </span>
          {!isLoading && items.length > 0 && (
            <span className="text-xs text-slate-500 ml-1">
              {items.length} {language === 'zh' ? '条' : 'items'}
            </span>
          )}
          {updatedAt && (
            <span className="flex items-center gap-1 text-xs text-slate-500 ml-2">
              <Clock className="w-3 h-3" />
              {timeAgo(updatedAt, language)}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {/* Body */}
      {open && (
        <div className="px-4 pb-4">
          {isLoading ? (
            <div className="py-6 text-center text-slate-500 text-sm">
              {language === 'zh' ? '加载中…' : 'Loading…'}
            </div>
          ) : items.length === 0 ? (
            <div className="py-6 text-center text-slate-500 text-sm">
              {language === 'zh' ? '暂无新闻' : 'No news yet'}
            </div>
          ) : (
            <>
              <div className="divide-y divide-white/5">
                {visible.map((item, i) => (
                  <div key={item.url + i} className="py-2.5 flex gap-3 items-start group">
                    {/* Tier dot */}
                    <span
                      className="mt-1.5 shrink-0 w-2 h-2 rounded-full"
                      style={{ background: TIER_DOT[item.tier] ?? '#94a3b8' }}
                      title={language === 'zh' ? TIER_LABEL_ZH[item.tier] : TIER_LABEL_EN[item.tier]}
                    />

                    <div className="min-w-0 flex-1">
                      {/* Title */}
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-start gap-1 text-sm text-slate-200 hover:text-white leading-snug group-hover:underline"
                      >
                        <span className="flex-1">{item.title}</span>
                        <ExternalLink className="w-3 h-3 shrink-0 mt-0.5 text-slate-500 group-hover:text-slate-300" />
                      </a>

                      {/* Meta */}
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1">
                        <span className="text-xs text-slate-500">{item.source}</span>
                        <span className="text-xs text-slate-600">·</span>
                        <span className="text-xs text-slate-500">{timeAgo(item.published, language)}</span>

                        {item.keywords?.slice(0, 3).map(kw => (
                          <span
                            key={kw}
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: 'rgba(255,215,0,0.1)', color: '#FFD700' }}
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {items.length > 8 && (
                <button
                  onClick={() => setShowAll(v => !v)}
                  className="mt-2 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  {showAll
                    ? (language === 'zh' ? '收起' : 'Show less')
                    : (language === 'zh' ? `查看全部 ${items.length} 条` : `Show all ${items.length}`)}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
