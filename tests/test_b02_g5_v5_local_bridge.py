"""Isolated unit tests. No Docker, real git or database connections."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, call

SOURCE = Path(__file__).resolve().parents[1] / 'tools' / 'b02_g5_v5_local_bridge.py'
if not SOURCE.exists():
    SOURCE = Path(__file__).with_name('b02_g5_v5_local_bridge.py')
spec = importlib.util.spec_from_file_location('b02_g5_v5_local_bridge', SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class LocalBridgeTests(unittest.TestCase):
    def test_wrong_target_does_not_call_git(self):
        with patch.object(bridge, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'STOP_TARGET_NOT_ALLOWLISTED'):
                bridge.validate_checkout('arbitrary_script.py')
            command.assert_not_called()

    def test_branch_guard_stops_before_any_docker(self):
        with patch.object(bridge, 'command', return_value='main') as command:
            with self.assertRaisesRegex(RuntimeError, 'STOP_BRANCH_MISMATCH'):
                bridge.validate_checkout('tools/b02_g5_v5_policy_runner.py')
            self.assertEqual(command.call_count, 1)

    def test_head_guard_stops_on_divergence(self):
        with patch.object(bridge, 'command', side_effect=[bridge.BRANCH, 'local', 'remote', 'remote\trefs/heads/' + bridge.BRANCH]):
            with self.assertRaisesRegex(RuntimeError, 'STOP_HEAD_NOT_RECONCILED'):
                bridge.validate_checkout('tools/b02_g5_v5_policy_runner.py')

    def test_dirty_tree_fails_without_modification(self):
        with patch.object(bridge, 'command', side_effect=[bridge.BRANCH, 'same', 'same', 'same\trefs/heads/' + bridge.BRANCH, ' M app/models.py']):
            with self.assertRaisesRegex(RuntimeError, 'STOP_TRACKED_FILES_MODIFIED'):
                bridge.validate_checkout('tools/b02_g5_v5_policy_runner.py')

    def test_protected_container_volume_required(self):
        with patch.object(bridge, 'command', return_value='[{"Mounts": [], "State": {"Running": false}}]'):
            with self.assertRaisesRegex(RuntimeError, 'STOP_PROTECTED_VOLUME_NOT_VERIFIED'):
                bridge.container_info()

    def test_stopped_container_started_and_restored(self):
        with patch.object(bridge, 'container_info', return_value={'State': {'Running': False}}), \
             patch.object(bridge, 'ready_within') as ready, \
             patch.object(bridge, 'no_other_clients', return_value=True), \
             patch.object(bridge, 'command') as command:
            with bridge.managed_container():
                ready.assert_called_once()
            self.assertEqual(command.call_args_list, [call('docker', 'start', bridge.CONTAINER),
                                                      call('docker', 'stop', bridge.CONTAINER, timeout=35)])

    def test_existing_container_never_stopped(self):
        with patch.object(bridge, 'container_info', return_value={'State': {'Running': True}}), \
             patch.object(bridge, 'ready_within'), \
             patch.object(bridge, 'command') as command:
            with bridge.managed_container():
                pass
            command.assert_not_called()

    def test_active_client_preserves_container(self):
        with patch.object(bridge, 'container_info', return_value={'State': {'Running': False}}), \
             patch.object(bridge, 'ready_within'), \
             patch.object(bridge, 'no_other_clients', return_value=False), \
             patch.object(bridge, 'command') as command:
            with bridge.managed_container():
                pass
            self.assertEqual(command.call_args_list, [call('docker', 'start', bridge.CONTAINER)])

    def test_loopback_ephemeral_and_closed(self):
        with bridge.loopback_transport() as port:
            self.assertGreater(port, 0)
            self.assertLess(port, 65536)


if __name__ == '__main__':
    unittest.main()
