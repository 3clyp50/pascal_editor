"""Lifecycle checks; run with unittest discover in the Agent Zero framework."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from helpers import plugins
from usr.plugins.pascal_editor import hooks
from usr.plugins.pascal_editor.helpers import mcp, runtime


class LifecycleTests(unittest.TestCase):
    def test_dependency_download_reuse_checksum_and_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            deps = Path(directory) / '.deps'
            node_dir = deps / 'node'
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:xz') as archive:
                node = tarfile.TarInfo(hooks.NODE_ARCHIVE + '/bin/node')
                node.mode = 0o755
                node.size = 4
                archive.addfile(node, io.BytesIO(b'node'))
            payload = stream.getvalue()
            with patch.object(runtime, 'DEPS_DIR', deps), patch.object(runtime, 'NODE_DIR', node_dir), patch.object(runtime.shutil, 'which', return_value=None), patch.object(hooks, 'NODE_SHA256', hashlib.sha256(payload).hexdigest()), patch.object(hooks.urllib.request, 'urlopen', return_value=io.BytesIO(payload)) as download:
                hooks.install_dependencies()
                self.assertEqual(Path(runtime.node_executable()).read_bytes(), b'node')
                with patch.object(hooks.subprocess, 'run', return_value=Mock(stdout='22.22.0\n')):
                    hooks.install_dependencies()
                download.assert_called_once()
                saved = Path(directory) / 'scene.db'
                saved.write_bytes(b'keep')
                with patch.object(mcp, 'register') as unregister, patch.object(runtime, 'stop_runtime') as stop:
                    hooks.uninstall()
                    hooks.uninstall()
                    unregister.assert_called_with(remove=True)
                    self.assertEqual(stop.call_count, 2)
                self.assertFalse(deps.exists())
                self.assertEqual(saved.read_bytes(), b'keep')
                with patch.object(hooks.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
                    with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                        hooks.install_dependencies()
                self.assertFalse(node_dir.exists())
                self.assertEqual(list(deps.iterdir()), [])

    def test_system_node_needs_no_download(self):
        with patch.object(runtime, 'node_executable', return_value='/usr/bin/node'), patch.object(hooks.subprocess, 'run', return_value=Mock(stdout='22.13.0\n')), patch.object(hooks.urllib.request, 'urlopen') as download:
            hooks.install_dependencies()
            download.assert_not_called()

    def test_automatic_initialization_and_failure_cleanup(self):
        with patch.object(plugins, 'get_toggle_state', return_value='enabled'), patch.object(runtime, 'get_config', return_value={}), patch.object(hooks, 'install_dependencies') as deps, patch.object(runtime, 'is_running', return_value=False), patch.object(runtime, 'ensure_running', return_value={'state': 'running'}) as start, patch.object(runtime, 'stop_runtime') as stop, patch.object(mcp, 'install') as install:
            hooks.install()
            deps.assert_called_once()
            start.assert_called_once_with()
            install.assert_called_once_with(activate=True)
            stop.assert_not_called()
            hooks.install(activate=False)
            install.assert_called_with(activate=False)
            install.side_effect = RuntimeError('MCP failed')
            with self.assertRaisesRegex(RuntimeError, 'MCP failed'):
                hooks.install()
            stop.assert_called_once()
            install.reset_mock(side_effect=True)
            start.return_value = {'state': 'timeout'}
            with self.assertRaisesRegex(RuntimeError, 'initialization failed'):
                hooks.install()
            install.assert_not_called()
            self.assertEqual(stop.call_count, 2)

    def test_disabled_plugin_does_not_install_or_start(self):
        for toggle, config in [('disabled', {}), ('enabled', {'enabled': False})]:
            with self.subTest(toggle=toggle, config=config), patch.object(plugins, 'get_toggle_state', return_value=toggle), patch.object(runtime, 'get_config', return_value=config), patch.object(hooks, 'install_dependencies') as deps, patch.object(runtime, 'ensure_running') as start, patch.object(runtime, 'stop_runtime') as stop, patch.object(mcp, 'register') as register:
                hooks.install(activate=False)
                deps.assert_not_called()
                start.assert_not_called()
                stop.assert_called_once()
                register.assert_called_once_with(remove=True, activate=False)


if __name__ == '__main__':
    unittest.main()
