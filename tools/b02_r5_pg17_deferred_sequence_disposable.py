#!/usr/bin/env python3
"""B02 R5: real PostgreSQL 17.10 constraint-order experiment, DISPOSABLE ONLY.

Uses exactly one temporary postgres:17.10-trixie container:
 - --pull=never --network none; NO ports, Docker volumes or host mounts;
 - in-memory tmpfs PGDATA, removed afterwards;
 - all DDL/DML within a SQL BEGIN..ROLLBACK in the throwaway database;
 - never connects to solveris_b02_r4g_test, cannot sign/release G5;
 - NEVER changes protected database/container.
This is a causal SQL *model*, not the production 0064/0065 migration.
"""
from __future__ import annotations
import subprocess
import sys
import time
from uuid import uuid4

IMAGE="postgres:17.10-trixie"
TIMEOUT=35
SQL=r"""
\set ON_ERROR_STOP on
BEGIN;
DO $do$
BEGIN
  IF current_setting('server_version') NOT LIKE '17.10%' THEN
    RAISE EXCEPTION 'STOP_DISPOSABLE_POSTGRES_17_10_REQUIRED';
  END IF;
END
$do$;

CREATE TABLE public.acquisition_mode_bindings(unit text PRIMARY KEY);
CREATE TABLE public.noncredential_acquisition_receipts(unit text PRIMARY KEY);
CREATE TABLE public.noncredential_sanitization_verifications(unit text PRIMARY KEY);
CREATE TABLE public.acquisition_executions(unit text PRIMARY KEY);
CREATE TABLE public.normative_artifacts(unit text PRIMARY KEY);

CREATE FUNCTION public.b02_deferred_complete_unit() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE table_name text; n integer;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
     'acquisition_mode_bindings','noncredential_acquisition_receipts',
     'noncredential_sanitization_verifications','acquisition_executions',
     'normative_artifacts'] LOOP
    EXECUTE format('SELECT count(*) FROM public.%I WHERE unit=$1',table_name)
      INTO n USING NEW.unit;
    IF n<>1 THEN
      RAISE EXCEPTION 'B02_INCOMPLETE_UNIT:%:%',NEW.unit,table_name;
    END IF;
  END LOOP;
  RETURN NULL;
END
$fn$;

CREATE CONSTRAINT TRIGGER z_b02_complete_unit
AFTER INSERT ON public.acquisition_mode_bindings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_deferred_complete_unit();
CREATE CONSTRAINT TRIGGER z_b02_complete_unit
AFTER INSERT ON public.noncredential_acquisition_receipts
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_deferred_complete_unit();
CREATE CONSTRAINT TRIGGER z_b02_complete_unit
AFTER INSERT ON public.noncredential_sanitization_verifications
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_deferred_complete_unit();
CREATE CONSTRAINT TRIGGER z_b02_complete_unit
AFTER INSERT ON public.acquisition_executions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_deferred_complete_unit();
CREATE CONSTRAINT TRIGGER z_b02_complete_unit
AFTER INSERT ON public.normative_artifacts
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_deferred_complete_unit();

CREATE TABLE public.b02_g5_operational_approval_uses(
  approval text PRIMARY KEY);
CREATE FUNCTION public.b02_g5_assert_reserved_two_units() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE n integer;
BEGIN
  SELECT count(DISTINCT unit) INTO n FROM public.acquisition_mode_bindings;
  IF n<>2 THEN RAISE EXCEPTION 'G5_ONESHOT_TWO_DOCUMENTS_REQUIRED'; END IF;
  RETURN NULL;
END
$fn$;
CREATE CONSTRAINT TRIGGER trg_b02_g5_one_shot_requires_two_units
AFTER INSERT ON public.b02_g5_operational_approval_uses
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_g5_assert_reserved_two_units();

DO $do$
DECLARE n integer;
BEGIN
 SELECT count(*) INTO n FROM pg_catalog.pg_trigger
 WHERE tgname='z_b02_complete_unit' AND tgdeferrable
 AND tginitdeferred AND tgenabled='O';
 IF n<>5 THEN RAISE EXCEPTION 'B02_ORIGINAL_TRIGGER_SHAPE_DIVERGED'; END IF;
END
$do$;

-- Unit 1: original complete unit before forcing deferred checks immediate.
SET CONSTRAINTS public.z_b02_complete_unit DEFERRED;
INSERT INTO public.acquisition_mode_bindings VALUES('571');
INSERT INTO public.noncredential_acquisition_receipts VALUES('571');
INSERT INTO public.noncredential_sanitization_verifications VALUES('571');
INSERT INTO public.acquisition_executions VALUES('571');
INSERT INTO public.normative_artifacts VALUES('571');
SET CONSTRAINTS ALL IMMEDIATE;

-- Negative: without re-deferral, the first insertion of second unit fails.
DO $do$
BEGIN
  BEGIN
    INSERT INTO public.acquisition_mode_bindings VALUES('1245');
    RAISE EXCEPTION 'B02_NEGATIVE_MISSED';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'B02_INCOMPLETE_UNIT:%' THEN RAISE; END IF;
  END;
  RAISE NOTICE 'B02_EXPECTED_EARLY_SECOND_UNIT_STOP';
END
$do$;

-- Scoped defer: only the five ORIGINAL complete-unit triggers are deferred.
SET CONSTRAINTS public.z_b02_complete_unit DEFERRED;
INSERT INTO public.acquisition_mode_bindings VALUES('1245');
INSERT INTO public.noncredential_acquisition_receipts VALUES('1245');
INSERT INTO public.noncredential_sanitization_verifications VALUES('1245');
INSERT INTO public.acquisition_executions VALUES('1245');
INSERT INTO public.normative_artifacts VALUES('1245');
SET CONSTRAINTS ALL IMMEDIATE;

-- Reservation happens after both complete distinct units and never before.
INSERT INTO public.b02_g5_operational_approval_uses VALUES('synthetic-test-only');
DO $do$
DECLARE n integer;
BEGIN
 SELECT count(DISTINCT unit) INTO n FROM public.acquisition_mode_bindings;
 IF n<>2 THEN RAISE EXCEPTION 'B02_TWO_UNIT_INTEGRITY_FAILED'; END IF;
END
$do$;
ROLLBACK;
SELECT CASE WHEN to_regclass('public.acquisition_mode_bindings') IS NULL
                 AND to_regclass('public.b02_g5_operational_approval_uses') IS NULL
 THEN 'B02_DISPOSABLE_REDEFER_TWO_UNITS_PASS'
 ELSE 'B02_DISPOSABLE_ROLLBACK_INCOMPLETE' END AS verdict;
"""

def docker(*args,stdin=None,timeout=TIMEOUT,ok=True):
    cmd=["docker",*args]
    proc=subprocess.run(cmd,input=stdin,text=True,capture_output=True,timeout=timeout)
    if ok and proc.returncode:
        raise RuntimeError("STOP_DOCKER_DISPOSABLE:"+proc.stderr.strip()[-600:])
    return proc

def main():
    name="solveris-r5-disposable-"+uuid4().hex[:12]
    started=False
    try:
        # The image is already present in the user's Docker inventory; never pull.
        run=docker("run","--rm","--pull=never","-d","--name",name,
                   "--network","none",
                   "--tmpfs","/var/lib/postgresql/data:rw,size=256m",
                   "--tmpfs","/tmp:rw,size=64m",
                   "-e","POSTGRES_HOST_AUTH_METHOD=trust",
                   IMAGE)
        if not run.stdout.strip():raise RuntimeError("STOP_DISPOSABLE_NOT_STARTED")
        started=True
        for _ in range(35):
            ready=docker("exec",name,"pg_isready","-U","postgres","-d","postgres",
                         timeout=6,ok=False)
            if ready.returncode==0:break
            time.sleep(0.4)
        else:raise RuntimeError("STOP_DISPOSABLE_PG_NOT_READY")
        result=docker("exec","-i",name,"psql","-X","-q",
                      "-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres",
                      stdin=SQL,timeout=50)
        if "B02_EXPECTED_EARLY_SECOND_UNIT_STOP" not in result.stderr:
            raise RuntimeError("STOP_NEGATIVE_NOT_REPRODUCED")
        if "B02_DISPOSABLE_REDEFER_TWO_UNITS_PASS" not in result.stdout:
            raise RuntimeError("STOP_REDEFER_ROLLBACK_NOT_PASS")
        print("B02_PG17_REAL_ENGINE_EARLY_SECOND_UNIT_NEGATIVE_PASS")
        print("B02_PG17_REAL_ENGINE_SCOPED_REDEFER_AND_ONE_SHOT_ORDER_PASS")
        print("B02_PG17_DISPOSABLE_TRANSACTION_ROLLBACK_PASS")
        print("B02_R5_PG17_DISPOSABLE_SQL_CAUSAL_PASS_NOT_B02_0064_0065")
    finally:
        if started:
            docker("rm","-f",name,timeout=25,ok=False)

if __name__=="__main__":
    try:main()
    except (OSError,subprocess.TimeoutExpired,RuntimeError) as exc:
        print(str(exc)[:700])
        sys.exit(2)
