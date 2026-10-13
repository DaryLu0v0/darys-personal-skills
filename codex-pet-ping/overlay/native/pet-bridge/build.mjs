import { spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

if (process.platform !== 'win32') process.exit(0);
const here = dirname(fileURLToPath(import.meta.url));
const framework = join(process.env.SystemRoot || 'C:\\Windows', 'Microsoft.NET', 'Framework64', 'v4.0.30319');
mkdirSync(join(here, 'build'), { recursive: true });
const references = ['System.dll', 'System.Core.dll', 'System.Drawing.dll', 'System.Windows.Forms.dll', 'System.Web.Extensions.dll',
  'WPF/WindowsBase.dll', 'WPF/UIAutomationClient.dll', 'WPF/UIAutomationTypes.dll'];
const result = spawnSync(join(framework, 'csc.exe'), ['/nologo', '/target:exe', '/platform:x64', '/optimize+',
  `/out:${join(here, 'build', 'pet-bridge.exe')}`, ...references.map(r => `/reference:${join(framework, r)}`), join(here, 'Program.cs')],
  { stdio: 'inherit', windowsHide: true });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
