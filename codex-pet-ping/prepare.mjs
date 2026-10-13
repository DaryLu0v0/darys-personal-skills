import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(here, 'upstream.json'), 'utf8'));
const options = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i];
  const value = process.argv[i + 1];
  if (!['--source', '--destination'].includes(key) || !value || value.startsWith('--')) {
    throw new Error('Usage: node prepare.mjs [--source <local-upstream-clone>] [--destination <new-directory>]');
  }
  if (options[key]) throw new Error(`Duplicate option: ${key}`);
  options[key] = value;
}

const destination = options['--destination'] ? resolve(options['--destination']) : join(here, '.work', 'lolPing');
if (existsSync(destination)) throw new Error(`Refusing to overwrite existing directory: ${destination}`);
const source = options['--source'] ? resolve(options['--source']) : manifest.upstream.repository;
if (options['--source'] && !existsSync(source)) throw new Error(`Local upstream clone not found: ${source}`);

function containedPath(root, relative) {
  const target = resolve(root, relative);
  if (isAbsolute(relative) || !target.startsWith(resolve(root) + sep)) {
    throw new Error(`Invalid package path: ${relative}`);
  }
  return target;
}

function textHash(path) {
  return createHash('sha256').update(readFileSync(path, 'utf8').replace(/\r\n/g, '\n'), 'utf8').digest('hex');
}

function verify(path, expected) {
  if (textHash(path) !== expected) throw new Error(`Content hash mismatch: ${path}`);
}

const patch = containedPath(here, manifest.patch.path);
verify(patch, manifest.patch.sha256);
for (const file of manifest.files) {
  containedPath(destination, file.path);
  if (file.overlay) verify(containedPath(join(here, 'overlay'), file.path), file.sha256);
}

function git(args, cwd = here) {
  return execFileSync('git', args, { cwd, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', windowsHide: true }).trim();
}

try {
  console.log(`Preparing lolPing ${manifest.upstream.tag} at ${destination}`);
  mkdirSync(dirname(destination), { recursive: true });
  git(['clone', '--no-checkout', '--no-hardlinks', '-c', 'core.autocrlf=false', '--', source, destination]);
  git(['checkout', '--detach', manifest.upstream.commit], destination);
  if (git(['rev-parse', 'HEAD'], destination) !== manifest.upstream.commit) {
    throw new Error('Upstream commit does not match the pinned revision.');
  }
  git(['apply', '--check', patch], destination);
  git(['apply', patch], destination);
  for (const file of manifest.files.filter(file => file.overlay)) {
    const target = containedPath(destination, file.path);
    if (existsSync(target)) throw new Error(`Overlay would replace an upstream file: ${file.path}`);
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(containedPath(join(here, 'overlay'), file.path), target);
  }
  for (const file of manifest.files) verify(containedPath(destination, file.path), file.sha256);
  console.log(`Verified ${manifest.files.length} integration files against the saved source snapshot.`);
  console.log('Source is ready. Follow README.md to install dependencies and build.');
} catch (error) {
  if (error.stderr) console.error(error.stderr.toString().trim());
  console.error(error.message);
  console.error(`No cleanup was performed. Inspect any partial checkout at: ${destination}`);
  process.exitCode = 1;
}
