# Attribution

The embedded editor runtime is derived from the open-source Pascal editor: Pascal Group Inc. and contributors, https://github.com/pascalorg/editor, licensed under the MIT License. See `runtime/LICENSE`.

This Agent Zero integration plugin adds a local process manager, reverse proxy, WebUI surface registration, and settings. The integration plugin code is licensed under the MIT License in `LICENSE`.

## Local rendering repairs (2026-09-05)

The embedded build includes modifications to Pascal source at upstream revision `ab0aa8286a53a063d65c434b0929538890c2b6c1`:

- `patches/viewer-live-resize.patch`: immediate resize observation and a continuous frame clock that redraws resized buffers without restarting on every layout change.
- `patches/editor-live-drawer.patch`: synchronize the viewer height throughout bottom-sheet dragging and snap animations.

These patches are local modifications, not an official upstream release. Pascal's original MIT copyright and permission notice remain unchanged in `runtime/LICENSE` and `third_party_LICENSE.txt`. Existing dependency license files are retained in the vendored runtime.

## Bundled MCP integration

The plugin includes a locally adapted build of `@pascal-app/mcp` **1.0.0-beta.6** and `@pascal-app/core` **1.0.0-beta.5**, from https://github.com/pascalorg/editor. Both are MIT-licensed by Pascal Group Inc.; their original notice is included in `mcp/PASCAL_LICENSE.txt`. These package versions differ from the source revision used for the embedded editor; compatibility was tested through saved-scene storage and live editing.

- `mcp/server.mjs` is the MIT-licensed Agent Zero adapter. It adds explicit scene targeting and persistence for per-call stdio sessions, and excludes unsupported process-history, sampling, and headless GLB tools.
- `mcp/build.mjs` bundles the upstream implementations and rewrites built-in asset paths for the `/pascal` mount. This is a local adaptation, not an official Pascal release.
- `patches/editor-saved-scene-mount.patch` preserves the local changes to saved-scene fetch and EventSource URLs needed under `/pascal`.
- `mcp/dist/dependencies.json` identifies all 25 dependencies included in the MCP bundle and their versions, repositories, and declared licenses.
- `mcp/dist/THIRD_PARTY_NOTICES.txt` includes the full notices for those dependencies (MIT, ISC, BSD-3-Clause, and Apache-2.0); `mcp/dist/server.mjs.LEGAL.txt` retains linked source notices. These files must accompany any redistribution of the bundle.
- The React Three Fiber npm archive omits its root license; `mcp/licenses/react-three-fiber.txt` retains the MIT notice obtained from its upstream v9.7.0 tag. Lingo's distinct copyright notice is retained in the generated third-party notices.

The integration does not claim ownership of upstream components or relicense them. The plugin's MIT license applies to its integration code, not as a replacement for third-party license terms.

