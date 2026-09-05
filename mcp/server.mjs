// MIT — Agent Zero integration; Pascal's tool implementations remain upstream.
import { SceneBridge } from '@pascal-app/mcp/bridge';
import { createSceneStore } from '@pascal-app/mcp/storage';
import { createSceneOperations } from '@pascal-app/mcp/operations';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { registerTools } from './node_modules/@pascal-app/mcp/dist/tools/index.js';

// A0 creates a new process/session per call. Never rely on load_scene having
// selected an implicit scene in a previous call (or another chat).
const INDEPENDENT = new Set([
  'list_scenes', 'load_scene', 'get_project_status', 'delete_scene', 'rename_scene',
  'create_project', 'save_scene', 'list_templates', 'search_assets',
  'create_from_template', 'create_house_from_brief', 'generate_variants',
]);
// Undo history is process-local; sampling isn't advertised by A0's MCP client.
// Do not advertise tools which would silently do nothing or cannot work.
const UNAVAILABLE = new Set(['undo', 'redo', 'photo_to_scene', 'export_glb']);
const idSchema = z.string().min(1).max(64);
const versionSchema = z.number().int().positive();
const bridge = new SceneBridge();
bridge.loadDefault();
const store = await createSceneStore();
const operations = createSceneOperations({ bridge, store });
const server = new McpServer({ name: 'a0-pascal-editor', version: '1.0.0' });

async function loadTarget(id, expectedVersion) {
  const scene = await operations.loadStoredScene(id);
  if (!scene) throw new Error(`scene_not_found: ${id}`);
  if (expectedVersion !== undefined && scene.version !== expectedVersion) {
    throw new Error(`version_conflict: expected ${expectedVersion}, found ${scene.version}; inspect the scene before retrying`);
  }
  bridge.loadJSON(scene.graph);
  bridge.setActiveScene(scene);
  bridge.clearHistory();
  return scene;
}

function errorResult(error) {
  return { isError: true, content: [{ type: 'text', text: error instanceof Error ? error.message : String(error) }] };
}

// Decorate the public registration boundary, not SDK private tool registries.
// A process-local queue also makes multiple calls in one stdio session safe.
let tail = Promise.resolve();
const registrar = {
  registerTool(name, config, handler) {
    if (UNAVAILABLE.has(name)) return;
    const required = !INDEPENDENT.has(name);
    const targetable = required || name === 'save_scene' || name === 'generate_variants';
    const inputSchema = { ...config.inputSchema };
    if (targetable) {
      inputSchema.sceneId = (required ? idSchema : idSchema.optional()).describe(
        'Saved Pascal scene ID. Explicit on every call; no implicit active scene is shared across calls or chats.',
      );
      if (!inputSchema.expectedVersion) inputSchema.expectedVersion = versionSchema.optional();
    }
    const description = config.description + (required
      ? ' Agent Zero: supply sceneId on EVERY call. Changes are saved to that scene and streamed to its editor view.'
      : ' Agent Zero: saved scenes open at /pascal/scene/<id>. New scenes must be persisted; no cross-call in-memory state.');
    return server.registerTool(name, { ...config, inputSchema, description }, (args, extra) => {
      const task = tail.then(async () => {
        try {
          const { sceneId, ...rest } = args;
          const params = { ...rest };
          if (name === 'create_project' && params.id && await operations.loadStoredScene(params.id)) {
            throw new Error('scene_already_exists: use editing tools to change an existing scene');
          }
          if (name === 'save_scene' && !sceneId && !params.id && params.includeCurrentScene !== false) {
            throw new Error('sceneId is required to save an existing scene; to import a graph set includeCurrentScene=false');
          }
          const target = sceneId || (name === 'generate_variants' ? params.baseSceneId : undefined);
          if (sceneId && name === 'save_scene' && params.id && params.id !== sceneId) {
            throw new Error('scene_id_mismatch: id and sceneId must refer to the same scene');
          }
          if (target) {
            const scene = await loadTarget(target, params.expectedVersion);
            if (name === 'save_scene') {
              params.id = scene.id;
              params.expectedVersion = scene.version;
            }
          } else if (name === 'generate_variants') {
            throw new Error('sceneId or baseSceneId is required');
          } else if (name === 'save_scene' && params.id) {
            const scene = await loadTarget(params.id, params.expectedVersion);
            params.expectedVersion = scene.version;
          }
          if (name === 'create_project' || name === 'create_from_template' || name === 'create_house_from_brief') {
            bridge.setScene({}, []);
            bridge.clearActiveScene();
            bridge.loadDefault();
          }
          if (name === 'create_from_template' || name === 'generate_variants') {
            // Unsaved graphs cannot survive A0's per-call process lifetime.
            params.save = true;
          }
          const result = await handler(params, extra);
          if (result.isError) return result;
          if (name === 'create_project') {
            // The local upstream store otherwise creates only an in-memory
            // placeholder, which vanishes when A0 closes this MCP process.
            const active = bridge.getActiveScene();
            const graph = operations.exportSceneGraph();
            const meta = await operations.saveScene({ ...active, graph, saveMode: 'draft', operation: name });
            bridge.setActiveScene(meta);
            await operations.appendSceneEvent({ sceneId: meta.id, version: meta.version, kind: name, graph });
            const payload = z.object(config.outputSchema).parse({ ...result.structuredContent, ...meta,
              isEmpty: false, latestVersion: meta.version, publishedVersion: meta.version,
              browserVisibleVersion: meta.version, nextStep: 'Pass this id as sceneId on every editing tool call.' });
            return { content: [{ type: 'text', text: JSON.stringify(payload) }], structuredContent: payload };
          }
          return result;
        } catch (error) {
          return errorResult(error);
        }
      });
      tail = task.then(() => {}, () => {});
      return task;
    });
  },
};
registerTools(registrar, operations);
await server.connect(new StdioServerTransport());
// No detached service, HTTP listener, token, or shared active-scene file.
process.stdin.on('end', () => { void server.close().finally(() => process.exit(0)); });
