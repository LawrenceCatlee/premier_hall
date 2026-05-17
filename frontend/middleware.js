import { next } from '@vercel/edge';

/**
 * Run only for SPA routes (paths without a file extension).
 * Excludes /assets/*, /data/*, favicon.ico, etc.
 */
export const config = {
  matcher: ['/((?!.*\\..*).*)', ],
};

export default function middleware(request) {
  const cookie = request.headers.get('cookie') ?? '';

  // User already has a language preference (set manually or by a previous visit)
  if (cookie.includes('plhall_lang=')) return next();

  const country = request.headers.get('x-vercel-ip-country') ?? '';
  const lang = country === 'CN' ? 'zh' : 'en';

  const response = next();
  response.headers.append(
    'Set-Cookie',
    `plhall_lang=${lang}; Path=/; Max-Age=2592000; SameSite=Lax`,
  );
  return response;
}
