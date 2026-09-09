"""Run from /a0: /opt/venv-a0/bin/python -m unittest discover -s usr/plugins/pascal_editor/tests -v"""
import asyncio
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from usr.plugins.pascal_editor import hooks
from usr.plugins.pascal_editor.helpers import mcp as integration, proxy
from helpers.mcp_handler import MCPServerLocal


class RegistrationTests(unittest.TestCase):
    def test_install_idempotent_preserves_unrelated_and_preferences(self):
        original = {"mcpServers": {"other": {"command": "unrelated", "disabled": True}}, "metadata": 42}
        once, changed = integration.merge_registration(json.dumps(original))
        self.assertTrue(changed)
        config = json.loads(once)
        config["mcpServers"]["pascal_editor"].update(disabled=True, disabled_tools=["delete_scene"], tool_timeout=77)
        raw = json.dumps(config)
        twice, changed = integration.merge_registration(raw)
        self.assertFalse(changed)
        self.assertEqual(raw, twice)
        removed, changed = integration.merge_registration(twice, remove=True)
        self.assertTrue(changed)
        self.assertEqual(json.loads(removed), original)
        self.assertFalse(integration.merge_registration(removed, remove=True)[1])

    def test_supported_shapes(self):
        for original in [[], {"mcpServers": []}, {"name": "other", "command": "test"}, {}]:
            with self.subTest(original=original):
                added, changed = integration.merge_registration(json.dumps(original))
                self.assertTrue(changed)
                self.assertFalse(integration.merge_registration(added)[1])
                removed, changed = integration.merge_registration(added, remove=True)
                self.assertTrue(changed)
                self.assertNotIn('"pascal_editor"', removed)

    def test_reject_malformed_and_name_collisions(self):
        for raw in ['{broken', '{"mcpServers": 3}', 'null', '{"unexpected": 1}']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                integration.merge_registration(raw)
        for name in ['pascal_editor', 'Pascal-Editor', 'pascal.editor', 'pascal editor']:
            raw = json.dumps({"mcpServers": {name: {"command": "not-ours"}}})
            with self.subTest(name=name), self.assertRaises(ValueError):
                integration.merge_registration(raw)
            self.assertEqual(integration.merge_registration(raw, remove=True), (raw, False))

    def test_registration_changes_only_mcp_setting(self):
        from helpers import settings
        state = {'mcp_servers': '{"mcpServers":{"other":{"command":"keep"}}}', 'untouched': 'sentinel'}
        writes = []
        def save(delta, apply):
            self.assertFalse(apply)
            self.assertEqual(set(delta), {'mcp_servers'})
            state.update(delta)
            writes.append(delta)
        with patch.object(settings, 'get_settings', return_value=state), patch.object(settings, 'set_settings_delta', side_effect=save), patch.object(integration, '_refresh_live') as refresh:
            integration.register()
            integration.register()
            self.assertEqual(len(writes), 1)
            integration.register(remove=True)
            self.assertEqual(len(writes), 2)
            self.assertEqual(json.loads(state['mcp_servers']), {'mcpServers': {'other': {'command': 'keep'}}})
            self.assertEqual(refresh.call_count, 3)

    def test_failed_initialization_restores_registration(self):
        from helpers import settings
        original = '{"mcpServers":{"other":{"command":"keep"}}}'
        state = {'mcp_servers': original}
        def save(delta, apply):
            self.assertFalse(apply)
            state.update(delta)
        with patch.object(settings, 'get_settings', return_value=state), patch.object(settings, 'set_settings_delta', side_effect=save), patch.object(integration, '_refresh_live', side_effect=RuntimeError('initialization failed')):
            with self.assertRaises(RuntimeError):
                integration.register()
            self.assertEqual(state['mcp_servers'], original)

    def test_real_install_uninstall_hooks_preserve_other_live_servers(self):
        from helpers import settings
        from helpers.mcp_handler import MCPConfig
        from types import SimpleNamespace
        original = '{"mcpServers":{"other":{"command":"keep"}}}'
        state = {'mcp_servers': original}
        other = SimpleNamespace(name='other')
        config = SimpleNamespace(servers=[other], disconnected_servers=[])
        def save(delta, apply):
            self.assertFalse(apply)
            state.update(delta)
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, 'get_settings', return_value=state), patch.object(settings, 'set_settings_delta', side_effect=save), patch.object(MCPConfig, 'get_instance', return_value=config), patch.object(MCPConfig, 'clear_project_instances'), patch.object(integration.runtime, 'stop_runtime'), patch.object(integration.runtime, 'ensure_running', return_value={'state': 'running'}), patch.object(hooks, 'install_dependencies'), patch.object(hooks.runtime, 'DEPS_DIR', Path(directory) / '.deps'):
            hooks.install()
            self.assertIs(config.servers[0], other)
            self.assertEqual(len(config.servers[1].get_tools()), 40)
            hooks.install()
            self.assertEqual(len(config.servers), 2)
            self.assertIs(config.servers[0], other)
            hooks.uninstall()
            self.assertEqual(config.servers, [other])
            self.assertEqual(json.loads(state['mcp_servers']), json.loads(original))

    def test_disabled_install_does_not_require_node(self):
        from helpers import plugins
        with patch.object(plugins, 'get_toggle_state', return_value='disabled'), patch.object(integration, 'prepare') as prepare, patch.object(integration, 'register') as register:
            integration.install()
            prepare.assert_not_called()
            register.assert_called_once_with(remove=True, activate=True)

    def test_launcher_rejects_disabled_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'mcp').mkdir()
            shutil.copy(integration.ENTRY, root/'mcp/launch.mjs')
            (root/'.toggle-0').touch()
            result = subprocess.run(['node', str(root/'mcp/launch.mjs')], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn('disabled', result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertFalse((root/'runtime/.data').exists())


class ProxyTests(unittest.TestCase):
    def test_small_sse_chunks_are_not_buffered(self):
        class Response:
            status = 200
            chunks = iter([b'retry: 1000\n\n', b'event: scene\ndata: {}\n\n', b''])
            def getheaders(self): return [('Content-Type', 'text/event-stream')]
            def read1(self, _size): return next(self.chunks)
        class Connection:
            def __init__(self, *args, **kwargs): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return Response()
            def close(self): pass
        items = queue.Queue()
        with patch.object(proxy.http.client, 'HTTPConnection', Connection):
            proxy._worker(items, 'GET', '/pascal/events', b'', {}, threading.Event())
        self.assertEqual(items.get()[0], 'meta')
        self.assertEqual(items.get(), b'retry: 1000\n\n')
        self.assertIn(b'event: scene', items.get())
        self.assertIsNone(items.get())


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_a0_separate_call_sessions_persist_and_isolate_scenes(self):
        with tempfile.TemporaryDirectory() as directory:
            server = MCPServerLocal({
                'name': 'pascal_test', 'command': 'node',
                'args': [str(integration.MCP_DIR/'dist/server.mjs')],
                'env': {**os.environ, 'PASCAL_DATA_DIR': directory, 'PASCAL_DB_PATH': directory+'/pascal.db', 'PASCAL_EDITOR_ORIGIN': '/pascal'},
                'init_timeout': 30, 'tool_timeout': 30,
            })
            await server.initialize()
            self.assertFalse(server.get_error(), server.get_error())
            tools = {tool['name']: tool for tool in server.get_tools()}
            self.assertEqual(len(tools), 40)
            self.assertTrue({'create_room', 'create_wall', 'add_door', 'list_scenes'} <= tools.keys())
            self.assertFalse({'undo', 'redo', 'photo_to_scene', 'export_glb'} & tools.keys())
            self.assertIn('sceneId', tools['create_wall']['input_schema']['required'])

            async def call(name, args, error=False):
                result = await server.call_tool(name, args)
                self.assertEqual(bool(result.isError), error, (name, result))
                return result.structuredContent if not error else result

            first = await call('create_project', {'name': 'First'})
            second = await call('create_project', {'name': 'Second'})
            self.assertEqual(first['editorUrl'], '/pascal/scene/'+first['id'])
            room = await call('create_room', {'sceneId': first['id'], 'levelId': first['defaultLevelId'], 'name': 'MCP test room', 'polygon': [[0,0],[4,0],[4,3],[0,3]]})
            door = await call('add_door', {'sceneId': first['id'], 'wallId': room['wallIds'][0], 't': 0.5})
            graph = await call('get_scene', {'sceneId': first['id']})
            self.assertIn(door['doorId'], graph['nodes'])
            other = await call('get_scene', {'sceneId': second['id']})
            self.assertEqual(len(other['nodes']), 3)
            meta = await call('load_scene', {'id': first['id']})
            self.assertEqual(meta['version'], 3)
            await call('create_project', {'id': first['id'], 'name': 'Do not overwrite'}, error=True)
            await call('create_wall', {'sceneId': first['id'], 'expectedVersion': 1, 'levelId': first['defaultLevelId'], 'start': [7,0], 'end': [8,0]}, error=True)
            await call('get_scene', {'sceneId': 'missing'}, error=True)
            await call('save_scene', {'name': 'Ambiguous'}, error=True)
            self.assertEqual((await call('load_scene', {'id': first['id']}))['version'], 3)
            template = await call('create_from_template', {'id': 'empty-studio', 'name': 'Template', 'save': False})
            self.assertIn('scene', template)
            await call('load_scene', {'id': template['scene']['id']})
            await call('delete_scene', {'id': second['id'], 'expectedVersion': second['version']})
            scenes = await call('list_scenes', {})
            self.assertEqual(len(scenes['scenes']), 2)


if __name__ == '__main__':
    unittest.main()
