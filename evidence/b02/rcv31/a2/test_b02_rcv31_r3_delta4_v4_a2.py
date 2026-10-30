"""Only A2 source execution snapshot delta; no Docker, PG, or protected writes."""
from pathlib import Path
import importlib.util, hashlib, os, shutil, tempfile, unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parent
SOURCE=BASE/'B02_RCV31_R3_CONCRETE_PATH_DELTA4_V4_A2_SNAPSHOT_CANDIDATO.py'
OBSERVER=BASE/'B02_RCV31_R3_OBSERVADOR_REAL_RUNNERDIR.py'
spec=importlib.util.spec_from_file_location('b02_rcv31_a2_v4',SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class A2FrozenObserverTests(unittest.TestCase):
 def test_original_observer_bytes_recovered_and_pinned(self):
  self.assertEqual(hashlib.sha256(OBSERVER.read_bytes()).hexdigest(),module.OBSERVER_PIN)

 def test_same_pinned_bytes_execute_in_separate_process(self):
  r=module.run_pinned_observer_source(OBSERVER,OBSERVER.read_bytes(),['--help'],os.environ.copy(),BASE)
  self.assertEqual(r.returncode,0,r.stderr.decode('utf8','replace')[-800:])
  self.assertIn(b'--trust-profile',r.stdout)

 def test_path_swapped_after_snapshot_does_not_change_executed_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   victim=Path(d)/OBSERVER.name
   shutil.copy2(OBSERVER,victim)
   captured=victim.read_bytes()
   # File path now points to an adversarial script, but bootstrap must never
   # re-read it as source. The archived observer --help still runs.
   victim.write_text('raise RuntimeError("SWAPPED_SOURCE_EXECUTED")\n',encoding='utf8')
   r=module.run_pinned_observer_source(victim,captured,['--help'],os.environ.copy(),BASE)
   self.assertEqual(r.returncode,0,r.stderr.decode('utf8','replace')[-800:])
   self.assertIn(b'--trust-profile',r.stdout)

 def test_initial_unpinned_bytes_fail_before_spawning(self):
  with patch.object(module.subprocess,'run',side_effect=AssertionError('must not spawn')):
   with self.assertRaisesRegex(RuntimeError,'OBSERVER_PRECOMMIT_SOURCE_BYTES_DIVERGENT'):
    module.run_pinned_observer_source(OBSERVER,b'print("forged")\n',[],os.environ.copy(),BASE)

 def test_pinned_reader_is_frozen_before_operate(self):
  src=SOURCE.read_text(encoding='utf8')
  ix_frozen=src.index(' observer_source=observer_script.read_bytes()')
  ix_operate=src.index('   result=opm.operate(')
  self.assertLess(ix_frozen,ix_operate)
  self.assertIn('p=run_pinned_observer_source(observer_script,observer_source,args,env,source_root)',src)
  self.assertNotIn('subprocess.run(args,env=env,cwd=source_root',src)

if __name__=='__main__':unittest.main(verbosity=2)