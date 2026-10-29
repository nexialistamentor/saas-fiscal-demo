"""Read-only G5 physical inventory; does not install/activate G5."""
from pathlib import Path
import importlib.util, json, sys
ROOT=Path(__file__).resolve().parents[1]
BRANCH="candidate/g5-successor-window-prep"
PAYLOAD=r'''
import json,os
from sqlalchemy import create_engine,text
from sqlalchemy.pool import NullPool
e=create_engine(os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"],poolclass=NullPool)
try:
 with e.connect() as c:
  c.exec_driver_sql("SET TRANSACTION READ ONLY")
  db,user,current,version=c.execute(text("SELECT current_database(),session_user,current_user,current_setting('server_version')")).one()
  if (db,user,current)!=("solveris_b02_r4g_test","solveris_b02_policy_writer","solveris_b02_policy_writer"):
   raise RuntimeError("G5_PHYSICAL_IDENTITY_STOP")
  revision=c.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
  names=["b02g5_assert_signature","b02g5_native_profile","b02g5_precommit_validate","b02_g5_assert_one_shot","b02_g5_operational_approval_uses"]
  funcs={}
  for n in names:
   funcs[n]=bool(c.execute(text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname=:n)"),{"n":n}).scalar_one())
  table=bool(c.execute(text("SELECT to_regclass('public.b02_g5_operational_approval_uses') IS NOT NULL")).scalar_one())
  print("G5_PHYSICAL_READ_ONLY|"+json.dumps({"db":db,"role":user,"postgres_version":version,"alembic_revision":revision,"g5_function_present":funcs,"g5_one_shot_table_present":table},sort_keys=True))
  c.rollback()
finally:
 e.dispose()
'''.encode("utf-8")
def main():
 if len(sys.argv)!=1:raise RuntimeError("STOP_UNEXPECTED_ARGS")
 spec=importlib.util.spec_from_file_location("g5_bridge",ROOT/"tools"/"b02_g4_authorized_runner.py")
 b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
 if b.git("branch","--show-current")!=BRANCH:raise RuntimeError("STOP_BRANCH")
 if b.git("rev-parse","HEAD")!=b.git("rev-parse","origin/"+BRANCH):raise RuntimeError("STOP_HEAD_DIVERGED")
 b.assert_repo_and_approval()
 started=False
 try:
  if not b.check_container():
   b.docker("start",b.CONTAINER);started=True
  rc,_=b.execute_exact_bridge(PAYLOAD)
  print("G5_PHYSICAL_INVENTORY_EXIT|"+str(rc))
  if rc:raise RuntimeError("STOP_G5_INVENTORY_FAILED")
 finally:
  if started:
   if b.other_clients()==0:
    b.docker("stop",b.CONTAINER);print("CONTAINER|RESTORED_STOPPED")
   else:print("CONTAINER|PRESERVED_RUNNING_ACTIVE_CLIENTS")
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("STOP|"+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__),file=sys.stderr);sys.exit(2)
