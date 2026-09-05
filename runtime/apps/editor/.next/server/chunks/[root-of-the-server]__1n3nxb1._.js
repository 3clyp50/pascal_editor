module.exports=[802178,e=>{e.v(t=>Promise.all(["server/chunks/[externals]_bun_sqlite_1aygq0y._.js"].map(t=>e.l(t))).then(()=>t(567551)))},902157,(e,t,n)=>{t.exports=e.x("node:fs",()=>require("node:fs"))},660526,(e,t,n)=>{t.exports=e.x("node:os",()=>require("node:os"))},750227,(e,t,n)=>{t.exports=e.x("node:path",()=>require("node:path"))},906677,56541,134172,e=>{"use strict";var t=e.i(666680),n=e.i(902157),r=e.i(660526),i=e.i(750227),s=e.i(469719);let a=/^[a-z0-9]+(?:-[a-z0-9]+)*$/,o="abcdefghijklmnopqrstuvwxyz0123456789";function d(e){let t=e.toLowerCase().replace(/\s+/g,"-").replace(/[^a-z0-9-]/g,"").replace(/-+/g,"-").replace(/^-+|-+$/g,"").slice(0,64).replace(/-+$/g,"");if(0===t.length)throw Error("Slug cannot be empty after sanitization");return t}function c(e){return"string"==typeof e&&0!==e.length&&!(e.length>64)&&a.test(e)}function l(){let e=(globalThis.crypto?.randomUUID?.().replace(/-/g,"")??function(){let e="";for(let t=0;t<24;t++)e+=o[Math.floor(Math.random()*o.length)];return e}()).toLowerCase().replace(/[^a-z0-9]/g,"");if(e.length>=12)return e.slice(0,12);let t=e;for(;t.length<12;)t+=o[Math.floor(Math.random()*o.length)];return t.slice(0,12)}async function u(t){if("Bun"in globalThis)return new(await e.A(802178)).Database(t,{create:!0,readwrite:!0});try{var n;return n=new(await Promise.resolve().then(()=>e.x("node:sqlite",()=>require("node:sqlite"),!0))).DatabaseSync(t),{exec(e){n.exec(e)},query(e){let t=n.prepare(e);return{all:(...e)=>t.all(...e),get:(...e)=>t.get(...e),run:(...e)=>t.run(...e)}},close(){n.close()}}}catch(n){let e=n instanceof Error?n.message:String(n);throw Error(`SQLite requires Bun or a Node runtime with node:sqlite support. Failed to open ${t}: ${e}`)}}e.s(["generateSlug",0,l,"isValidSlug",0,c,"sanitizeSlug",0,d],56541);class h extends Error{code="not_found";constructor(e="Scene not found"){super(e),this.name="SceneNotFoundError"}}class p extends Error{code="version_conflict";constructor(e="Scene version conflict"){super(e),this.name="SceneVersionConflictError"}}class _ extends Error{code="invalid";constructor(e="Scene invalid"){super(e),this.name="SceneInvalidError"}}class E extends Error{code="too_large";constructor(e="Scene too large"){super(e),this.name="SceneTooLargeError"}}e.s(["SceneInvalidError",0,_,"SceneNotFoundError",0,h,"SceneTooLargeError",0,E,"SceneVersionConflictError",0,p],134172);let g=s.z.object({nodes:s.z.record(s.z.string(),s.z.unknown()),rootNodeIds:s.z.array(s.z.string()),collections:s.z.record(s.z.string(),s.z.unknown()).optional(),materials:s.z.record(s.z.string(),s.z.unknown()).optional(),installedPlugins:s.z.array(s.z.string()).optional()});function T(e=process.env){if(e.PASCAL_DB_PATH&&e.PASCAL_DB_PATH.length>0)return e.PASCAL_DB_PATH;if(e.PASCAL_DATA_DIR&&e.PASCAL_DATA_DIR.length>0)return i.join(e.PASCAL_DATA_DIR,"pascal.db");let t=e.XDG_DATA_HOME;return t&&t.length>0?i.join(t,"pascal","data","pascal.db"):i.join(r.homedir(),".pascal","data","pascal.db")}function w(e){let t=m(e.id);return{id:e.id,name:e.name,projectId:e.project_id,ownerId:e.owner_id,thumbnailUrl:e.thumbnail_url,version:e.version,createdAt:e.created_at,updatedAt:e.updated_at,sizeBytes:e.size_bytes,nodeCount:e.node_count,editorUrl:t,url:t,published:!0,graphHash:S(e.graph_json)}}function m(e){let t=process.env.PASCAL_EDITOR_ORIGIN?.replace(/\/$/,"");return t?`${t}/scene/${encodeURIComponent(e)}`:`/editor/${e}`}function S(e){return(0,t.createHash)("sha256").update(e).digest("hex")}function v(e){let t=m(e.id);return{id:e.id,projectId:e.id,name:e.name,editorUrl:t,url:t,ownerId:e.ownerId,thumbnailUrl:e.thumbnailUrl,publishedVersion:null,latestVersion:null,draftVersion:null,browserVisibleVersion:null,version:0,isEmpty:!0,sizeBytes:0,nodeCount:0,graphHash:null,createdAt:e.createdAt,updatedAt:e.updatedAt}}function I(e){if("string"!=typeof e)throw new _("Scene name must be a string");if(e.trim().length<1||e.length>200)throw new _(`Scene name must be 1-200 characters (got ${e.length})`)}function N(e){return JSON.stringify(e)}function b(e,t){let n;try{n=JSON.parse(e)}catch(e){throw new _(`Failed to parse scene graph for ${t}: ${e instanceof Error?e.message:String(e)}`)}let r=g.safeParse(n);if(!r.success)throw new _(`Scene graph for ${t} has invalid shape: ${r.error}`);let i=r.data;for(let[e,n]of Object.entries(i.nodes)){if(!n||"object"!=typeof n||Array.isArray(n))throw new _(`Scene graph for ${t} has non-object node at "${e}"`);let r=n.type;if("string"!=typeof r||0===r.length)throw new _(`Scene graph for ${t} has node "${e}" missing a string "type"`)}return i}class f{backend="sqlite";databasePath;maxSceneBytes;projectPlaceholders=new Map;db=null;dbPromise=null;constructor(e={}){const t=e.env??process.env;this.databasePath=i.resolve(e.databasePath??T(t)),this.maxSceneBytes=function(e,t){if(void 0!==t){if(!Number.isInteger(t)||t<=0)throw new _("maxSceneBytes must be a positive integer");return t}let n=e?.PASCAL_MAX_SCENE_BYTES;if(void 0===n||""===n)return 0xa00000;let r=Number.parseInt(n,10);if(!Number.isInteger(r)||r<=0)throw new _("PASCAL_MAX_SCENE_BYTES must be a positive integer");return r}(t,e.maxSceneBytes)}async createProject(e){let t=await this.database();I(e.name);let n=e.id?d(e.id):this.generateUniqueId(t);if(!c(n))throw new _(`Invalid project id after sanitization: "${n}"`);if(this.getRow(t,n))throw new _(`Project with id "${n}" already exists`);let r=new Date().toISOString(),i={id:n,name:e.name,ownerId:e.ownerId??null,thumbnailUrl:null,createdAt:r,updatedAt:r};return this.projectPlaceholders.set(n,i),v(i)}async getProjectStatus(e){let t=await this.database(),n=d(e),r=this.getRow(t,n);if(r){let e;return e=m(r.id),{id:r.id,projectId:r.project_id??r.id,name:r.name,editorUrl:e,url:e,ownerId:r.owner_id,thumbnailUrl:r.thumbnail_url,publishedVersion:r.version,latestVersion:r.version,draftVersion:null,browserVisibleVersion:r.version,version:r.version,isEmpty:0===r.node_count,sizeBytes:r.size_bytes,nodeCount:r.node_count,graphHash:S(r.graph_json),createdAt:r.created_at,updatedAt:r.updated_at}}let i=this.projectPlaceholders.get(n);return i?v(i):null}async save(e){return this.withWriteTransaction(t=>{if(I(e.name),!e.graph||"object"!=typeof e.graph)throw new _("graph is required");let n=e.id,r=n?d(n):this.generateUniqueId(t);if(!c(r))throw new _(`Invalid scene id after sanitization: "${r}"`);let i=this.getRow(t,r),s=this.projectPlaceholders.get(r);if(i&&void 0!==n&&void 0===e.expectedVersion)throw new _(`Scene with id "${r}" already exists. Pass a different id or provide expectedVersion to overwrite.`);if(void 0!==e.expectedVersion){let t=i?.version??0;if(t!==e.expectedVersion)throw new p(`Scene "${r}" version mismatch: expected ${e.expectedVersion}, got ${t}`)}let a=N(e.graph),o=Buffer.byteLength(a,"utf8");if(o>this.maxSceneBytes)throw new E(`Scene "${r}" is ${o} bytes, exceeds cap of ${this.maxSceneBytes} bytes`);let l=new Date().toISOString(),u=(i?.version??0)+1,h=i?.created_at??s?.createdAt??l,g=Object.keys(e.graph.nodes??{}).length,T=e.projectId??i?.project_id??(s?r:null),w=e.ownerId??i?.owner_id??s?.ownerId??null,v=e.thumbnailUrl??i?.thumbnail_url??s?.thumbnailUrl??null;return i?t.query(`UPDATE scenes
             SET name = ?,
                 project_id = ?,
                 owner_id = ?,
                 thumbnail_url = ?,
                 version = ?,
                 updated_at = ?,
                 size_bytes = ?,
                 node_count = ?,
                 graph_json = ?
           WHERE id = ?`).run(e.name,T,w,v,u,l,o,g,a,r):t.query(`INSERT INTO scenes (
             id, name, project_id, owner_id, thumbnail_url, version,
             created_at, updated_at, size_bytes, node_count, graph_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(r,e.name,T,w,v,u,h,l,o,g,a),t.query(`INSERT INTO scene_revisions (
           scene_id, version, graph_json, author_kind, author_id, created_at
         ) VALUES (?, ?, ?, ?, ?, ?)`).run(r,u,a,"mcp",w,l),this.projectPlaceholders.delete(r),{id:r,name:e.name,projectId:T,ownerId:w,thumbnailUrl:v,version:u,createdAt:h,updatedAt:l,sizeBytes:o,nodeCount:g,editorUrl:m(r),url:m(r),published:!0,graphHash:S(a)}})}async load(e){let t=await this.database(),n=this.getRow(t,d(e));return n?{...w(n),graph:b(n.graph_json,n.id)}:null}async list(e={}){let t=[],n=[];void 0!==e.projectId&&(t.push("project_id = ?"),n.push(e.projectId)),void 0!==e.ownerId&&(t.push("owner_id = ?"),n.push(e.ownerId));let r=e.limit??100,i=Number.isInteger(r)&&r>=0?r:0;n.push(i);let s=t.length>0?`WHERE ${t.join(" AND ")}`:"";return(await this.database()).query(`SELECT id, name, project_id, owner_id, thumbnail_url, version,
                created_at, updated_at, size_bytes, node_count, graph_json
           FROM scenes
           ${s}
          ORDER BY updated_at DESC, id ASC
          LIMIT ?`).all(...n).map(e=>w(e))}async delete(e,t={}){return this.withWriteTransaction(n=>{let r=d(e),i=this.getRow(n,r);if(!i)return!1;if(void 0!==t.expectedVersion&&i.version!==t.expectedVersion)throw new p(`Scene "${r}" version mismatch: expected ${t.expectedVersion}, got ${i.version}`);return n.query("DELETE FROM scenes WHERE id = ?").run(r),!0})}async rename(e,t,n={}){return this.withWriteTransaction(r=>{I(t);let i=d(e),s=this.getRow(r,i);if(!s)throw new h(`Scene "${i}" not found`);if(void 0!==n.expectedVersion&&s.version!==n.expectedVersion)throw new p(`Scene "${i}" version mismatch: expected ${n.expectedVersion}, got ${s.version}`);let a=new Date().toISOString(),o=s.version+1;return r.query("UPDATE scenes SET name = ?, version = ?, updated_at = ? WHERE id = ?").run(t,o,a,i),r.query(`INSERT INTO scene_revisions (
             scene_id, version, graph_json, author_kind, author_id, created_at
           ) VALUES (?, ?, ?, ?, ?, ?)`).run(i,o,s.graph_json,"mcp",s.owner_id,a),{...w(s),name:t,version:o,updatedAt:a}})}async appendSceneEvent(e){return this.withWriteTransaction(t=>{let n=d(e.sceneId);if(!this.getRow(t,n))throw new h(`Scene "${n}" not found`);let r=N(e.graph),i=new Date().toISOString();return{eventId:Number(t.query(`INSERT INTO scene_events (
             scene_id, version, kind, created_at, graph_json
           ) VALUES (?, ?, ?, ?, ?)`).run(n,e.version,e.kind,i,r).lastInsertRowid),sceneId:n,version:e.version,kind:e.kind,createdAt:i,graph:e.graph}})}async listSceneEvents(e,t={}){let n=Math.max(0,t.afterEventId??0),r=t.limit??100,i=Number.isInteger(r)&&r>0?r:100;return(await this.database()).query(`SELECT event_id, scene_id, version, kind, created_at, graph_json
           FROM scene_events
          WHERE scene_id = ?
            AND event_id > ?
          ORDER BY event_id ASC
          LIMIT ?`).all(d(e),n,i).map(e=>({eventId:Number(e.event_id),sceneId:e.scene_id,version:Number(e.version),kind:e.kind,createdAt:e.created_at,graph:b(e.graph_json,`${e.scene_id}@${e.version}`)}))}close(){this.db?.close(),this.db=null,this.dbPromise=null}async database(){return this.db?this.db:(this.dbPromise||(this.dbPromise=(async()=>{(0,n.mkdirSync)(i.dirname(this.databasePath),{recursive:!0});let e=await u(this.databasePath);return e.exec("PRAGMA foreign_keys = ON"),e.exec("PRAGMA journal_mode = WAL"),e.exec("PRAGMA busy_timeout = 5000"),this.migrate(e),this.db=e,e})()),this.dbPromise)}migrate(e){e.exec(`
      CREATE TABLE IF NOT EXISTS scenes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL CHECK (length(name) >= 1 AND length(name) <= 200),
        project_id TEXT,
        owner_id TEXT,
        thumbnail_url TEXT,
        version INTEGER NOT NULL CHECK (version >= 1),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
        node_count INTEGER NOT NULL CHECK (node_count >= 0),
        graph_json TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS scenes_project_updated_idx
        ON scenes(project_id, updated_at DESC);

      CREATE INDEX IF NOT EXISTS scenes_owner_updated_idx
        ON scenes(owner_id, updated_at DESC);

      CREATE TABLE IF NOT EXISTS scene_revisions (
        scene_id TEXT NOT NULL,
        version INTEGER NOT NULL CHECK (version >= 1),
        graph_json TEXT NOT NULL,
        author_kind TEXT NOT NULL,
        author_id TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (scene_id, version),
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS scene_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id TEXT NOT NULL,
        version INTEGER NOT NULL CHECK (version >= 1),
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL,
        graph_json TEXT NOT NULL,
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS scene_events_scene_event_idx
        ON scene_events(scene_id, event_id);
    `)}async withWriteTransaction(e){let t=await this.database();t.exec("BEGIN IMMEDIATE");try{let n=await e(t);return t.exec("COMMIT"),n}catch(e){try{t.exec("ROLLBACK")}catch{}throw e}}getRow(e,t){var n;return(n=e.query(`SELECT id, name, project_id, owner_id, thumbnail_url, version,
                  created_at, updated_at, size_bytes, node_count, graph_json
             FROM scenes
            WHERE id = ?`).get(t))&&"object"==typeof n?n:null}generateUniqueId(e){for(let t=0;t<20;t++){let t=l();if(!this.getRow(e,t))return t}throw new _("Failed to generate a unique scene id")}}e.s(["SqliteSceneStore",0,f,"resolveDefaultDatabasePath",0,T],906677)}];

//# sourceMappingURL=%5Broot-of-the-server%5D__1n3nxb1._.js.map