// MIT — plugin-owned, on-demand stdio entrypoint. No global installs or daemon.
import { existsSync, readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
try {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 13)) throw new Error('Node.js 22.13 or newer is required');
  const configFile = path.join(root, 'config.json');
  const config = existsSync(configFile) ? JSON.parse(readFileSync(configFile, 'utf8')) : {};
  if (existsSync(path.join(root, '.toggle-0')) || config.enabled === false || config.mcp_enabled === false) {
    throw new Error('Pascal Editor MCP is disabled');
  }
  const data = path.join(root, 'runtime/.data');
  mkdirSync(data, { recursive: true });
  process.env.PASCAL_DATA_DIR = data;
  process.env.PASCAL_DB_PATH = path.join(data, 'pascal.db');
  process.env.PASCAL_EDITOR_ORIGIN = '/pascal';
  await import('./dist/server.mjs');
} catch (error) {
  console.error('[pascal-editor-mcp]', error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
