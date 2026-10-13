import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { PetRequest } from './petQuestion';

/** A temporary request and screenshot are removed after the pet has consumed the clipboard image. */
export async function sendPetQuestion(executable: string, tempRoot: string, request: PetRequest, signal?: AbortSignal): Promise<void> {
  const dir = await mkdtemp(join(tempRoot, 'lolping-pet-'));
  try {
    const path = join(dir, 'request.json');
    await writeFile(path, JSON.stringify({ ...request, imagePath: join(dir, 'marked.png') }), 'utf8');
    await new Promise<void>((resolve, reject) => {
      execFile(executable, [path], { windowsHide: true, timeout: 25000, maxBuffer: 32 * 1024, signal }, (error, stdout) => {
        try {
          const result = JSON.parse(stdout.trim()) as { ok?: boolean; message?: string };
          if (!error && result.ok === true) resolve();
          else reject(new Error(result.message || 'The pet did not accept the question.'));
        } catch {
          reject(new Error(error?.code === 'ENOENT' ? 'The pet helper is missing. Reinstall this build.' : 'The pet did not respond. Check that it is visible and try again.'));
        }
      });
    });
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => undefined);
  }
}
