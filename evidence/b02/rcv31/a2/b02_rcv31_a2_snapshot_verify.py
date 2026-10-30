"""RCV31 A2 V4 exact-source check. Pure local; no Docker, SQL, keys or protected writes."""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ARCHIVE='SOLVERIS_B02_DELTA4_V3_ENTREGA_COMPLEMENTAR_20261025_163045.zip'
PINS={
 'archive':'b90855ecc7a90a499b93b225516ae289ba98f2d8c1d35f597781d1b832a5a304',
 'source':'1fae5b1aefe9630e077eae9c98b44c91d4f9dd99f9e4560a6dab83b74e5e7779',
 'observer':'4dc2b18af2942353b788b43bf41a2b6ef37b406bb16c942f335c94f6bc369e2e',
 'patch':'bfd8b397bb245923a7cff10b0b1c06480bef29aa8e2c707691bcc992c5f8ce7e',
 'candidate':'2fd9c8b9fdae373ec7622971a6d5efdca0f3d18f5082769065f7cd1f0e6bda11'}
SOURCE='B02_RCV31_R3_CONCRETE_PATH_DELTA4_V3_SOBRE_REAL.py'
OBSERVER='B02_RCV31_R3_OBSERVADOR_REAL_RUNNERDIR.py'
PATCH='B02_RCV31_R3_DELTA4_V3_A2_SNAPSHOT_V4.patch'
CANDIDATE='B02_RCV31_R3_CONCRETE_PATH_DELTA4_V4_A2_SNAPSHOT_CANDIDATO.py'
TEST='test_b02_rcv31_r3_delta4_v4_a2.py'

def check(data,kind):
 h=hashlib.sha256(data).hexdigest()
 if h!=PINS[kind]:raise RuntimeError('STOP_'+kind.upper()+'_HASH_DIVERGENCE:'+h)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--archive',type=Path,default=Path.home()/'Downloads'/ARCHIVE)
 opts=ap.parse_args()
 if not opts.archive.is_file():raise RuntimeError('STOP_ARCHIVE_MISSING:'+str(opts.archive))
 root=Path(__file__).resolve().parent
 patch=root/PATCH
 tests=root/TEST
 if not patch.is_file() or not tests.is_file():raise RuntimeError('STOP_REPOSITORY_A2_SOURCE_MISSING')
 check(patch.read_bytes(),'patch')
 check(opts.archive.read_bytes(),'archive')
 with ZipFile(opts.archive) as z:
  if z.testzip() is not None:raise RuntimeError('STOP_CORRUPT_ARCHIVE')
  if SOURCE not in z.namelist() or OBSERVER not in z.namelist():
   raise RuntimeError('STOP_ARCHIVE_SOURCE_MISSING')
  original=z.read(SOURCE);observer=z.read(OBSERVER)
 check(original,'source');check(observer,'observer')
 with TemporaryDirectory(prefix='b02_a2_focal_') as temp:
  work=Path(temp)
  (work/SOURCE).write_bytes(original)
  (work/OBSERVER).write_bytes(observer)
  shutil.copy2(tests,work/TEST)
  for extra in ('--check',None):
   cmd=['git','-C',str(work),'apply']
   if extra:cmd.append(extra)
   cmd.append(str(patch))
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
   if r.returncode:raise RuntimeError('STOP_GIT_APPLY:'+r.stderr[-400:])
  changed_raw=(work/SOURCE).read_bytes()
  # Windows git apply can convert LF source to CRLF under core.autocrlf.
  # Canonicalize ONLY line endings before the immutable candidate hash check.
  # The exact pin still rejects any semantic or non-newline byte change.
  changed=changed_raw.replace(b'\r\n',b'\n')
  if b'\r' in changed:raise RuntimeError('STOP_MIXED_OR_UNSUPPORTED_CANDIDATE_NEWLINES')
  check(changed,'candidate')
  (work/SOURCE).write_bytes(changed)
  (work/CANDIDATE).write_bytes(changed)
  p=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(work),
     '-p',TEST,'-v'],capture_output=True,text=True,timeout=90)
  if p.returncode or 'Ran 5 tests' not in p.stderr or '\nOK' not in p.stderr:
   raise RuntimeError('STOP_A2_FOCAL_TESTS:'+p.stderr[-900:])
  print(json.dumps({'status':'RCV31_A2_V4_SOURCE_SNAPSHOT_LOCAL_5_OF_5_PASS',
   'candidate_sha256':PINS['candidate'],'source_sha256':PINS['source'],
   'observer_sha256':PINS['observer'],'writes_protected':0,
   'physical_postgresql_test':'NOT_RUN','institutional_review':'NOT_INFERRED'},sort_keys=True))

if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,ValueError) as e:
  print(str(e),file=sys.stderr)
  sys.exit(2)
