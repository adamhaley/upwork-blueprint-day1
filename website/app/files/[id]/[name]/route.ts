import fs from 'node:fs';
import path from 'node:path';
import { isLocal, json } from '@/lib/server/guard.mjs';
import { ID, JOBS_DIR } from '@/lib/server/root.mjs';
import { artifactPath, ARTIFACT_CSP } from '@/lib/server/artifact.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.md': 'text/plain; charset=utf-8', '.pdf': 'application/pdf',
  '.png': 'image/png', '.json': 'application/json; charset=utf-8',
};

// A job's own files (application, one-pager). Links and previews open
// them directly, so there is no token here, only the local host check and a path
// that cannot leave the job's folder.
export async function GET(req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  if (!isLocal(req)) return json({ error: 'local only' }, 403);
  const { id, name } = await params;
  const target = artifactPath(JOBS_DIR, id, name);
  if (!target) return json({ error: 'not found' }, 404);
  return new Response(fs.readFileSync(target), {
    headers: { 'content-type': TYPES[path.extname(name)] || 'application/octet-stream', 'cache-control': 'no-store',
      'x-content-type-options': 'nosniff', 'content-security-policy': ARTIFACT_CSP },
  });
}
