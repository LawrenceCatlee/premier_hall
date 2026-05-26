export async function fetchNews() {
  const res = await fetch('/data/news.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error(`Failed to load news: ${res.status}`);
  return res.json();
}
