// MIT — deterministic Node bundle; retain every bundled dependency's notices.
import { build } from 'esbuild';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
await mkdir(path.join(root, 'dist'), { recursive: true });
const result = await build({
  absWorkingDir: root,
  entryPoints: ['server.mjs'], outfile: 'dist/server.mjs',
  bundle: true, platform: 'node', target: 'node22', format: 'esm',
  external: ['bun:sqlite'], metafile: true, legalComments: 'linked',
  banner: { js: 'import { createRequire as __a0CreateRequire } from "node:module"; const require = __a0CreateRequire(import.meta.url);' },
  plugins: [{
    name: 'pascal-mounted-assets',
    setup(build) {
      build.onLoad({ filter: /node_modules\/@pascal-app\/(mcp|core)\/.*\.js$/ }, async ({ path: filename }) => ({
        contents: (await readFile(filename, 'utf8')).replace(/(["'`])\/(items|textures|icons)\//g, '$1/pascal/$2/'),
        loader: 'js',
      }));
    },
  }],
});
const packages = new Map();
for (const filename of Object.keys(result.metafile.inputs)) {
  if (!filename.includes('node_modules/')) continue;
  let directory = path.dirname(path.resolve(root, filename));
  while (directory.startsWith(root)) {
    try {
      const pkg = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8'));
      if (pkg.name && pkg.version) { packages.set(directory, pkg); break; }
    } catch {}
    directory = path.dirname(directory);
  }
}
let notices = 'Third-party software included in the Pascal MCP Node bundle\n\n';
const inventory = [];
for (const [directory, pkg] of [...packages].sort((a,b) => a[1].name.localeCompare(b[1].name))) {
  inventory.push({ name: pkg.name, version: pkg.version, license: pkg.license, repository: pkg.repository });
  notices += `\n${'='.repeat(72)}\n${pkg.name}@${pkg.version}\nLicense: ${JSON.stringify(pkg.license)}\n`;
  const files = (await readdir(directory)).filter(name => /^(license|licence|copying|notice)([.-]|$)/i.test(name));
  if (!files.length && pkg.name.startsWith('@pascal-app/')) {
    notices += await readFile(path.join(root, 'PASCAL_LICENSE.txt'), 'utf8');
  } else if (!files.length && pkg.name === '@react-three/fiber') {
    // Upstream npm archive omits the root license; copied from the v9.7.0 tag.
    notices += await readFile(path.join(root, 'licenses/react-three-fiber.txt'), 'utf8');
  } else {
    if (!files.length) throw new Error(`Missing license text for bundled dependency ${pkg.name}`);
    for (const file of files.sort()) notices += `\n--- ${file} ---\n${await readFile(path.join(directory, file), 'utf8')}\n`;
  }
}
await writeFile(path.join(root, 'dist/THIRD_PARTY_NOTICES.txt'), notices);
await writeFile(path.join(root, 'dist/dependencies.json'), JSON.stringify(inventory, null, 2) + '\n');
console.log(`Built Pascal MCP with notices for ${inventory.length} bundled dependencies.`);
