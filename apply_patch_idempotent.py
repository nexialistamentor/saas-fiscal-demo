path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# 1. Make PolicyVersion insertion idempotent: reuse if it already exists.
old = """        session.add(pv); session.flush()
        print("POLICY_VERSION_RECORD_HASH =", pv.record_hash)"""
new = """        existing_pv = session.query(models.PolicyVersion).filter_by(
            policy_id=pv.policy_id, policy_version=pv.policy_version, policy_hash=pv.policy_hash
        ).one_or_none()
        if existing_pv is not None:
            pv = existing_pv
            print("POLICY_VERSION_REUSED, RECORD_HASH =", pv.record_hash)
        else:
            session.add(pv); session.flush()
            print("POLICY_VERSION_RECORD_HASH =", pv.record_hash)"""
if old not in content: raise SystemExit("A_NOT_FOUND")
content = content.replace(old, new)

# 2. Make bootstrap insertion idempotent.
old2 = "        session.add(boot); session.flush()\n        print(\"BOOTSTRAP_RECORD_HASH =\", boot.record_hash)"
new2 = """        existing_boot = session.query(models.BootstrapAuthorityRecord).filter_by(
            bootstrap_authority_record_id=boot.bootstrap_authority_record_id
        ).one_or_none()
        if existing_boot is not None:
            boot = existing_boot
            print("BOOTSTRAP_REUSED, RECORD_HASH =", boot.record_hash)
        else:
            session.add(boot); session.flush()
            print("BOOTSTRAP_RECORD_HASH =", boot.record_hash)"""
if old2 not in content: raise SystemExit("B_NOT_FOUND")
content = content.replace(old2, new2)

# 3. Make each PolicyDecision insertion idempotent.
old3 = """            d.record_hash = hashlib.sha256(_cb(d_material)).hexdigest()
            session.add(d); session.flush()"""
new3 = """            d.record_hash = hashlib.sha256(_cb(d_material)).hexdigest()
            existing_d = session.query(models.PolicyDecision).filter_by(decision_id=decision_id).one_or_none()
            if existing_d is not None:
                d = existing_d
            else:
                session.add(d); session.flush()"""
if old3 not in content: raise SystemExit("C_NOT_FOUND")
content = content.replace(old3, new3)

# 4. Fix transaction handling: explicit commit/rollback, never implicit commit on clean exit.
old4 = """        if execute:
            session.commit()
            print("DECISIONS_COMMITTED")
        else:
            # Keep decisions visible to the second connection for the activation
            # dry-run (same values the writer will see at real execution time),
            # but still never persist them: flush only, rollback happens after
            # the activation attempt below so both stages are exercised.
            session.flush()
            print("DECISIONS_FLUSHED (not committed yet) -- testing activation stage too")

    with Session(writer_engine) as wsession, wsession.begin():"""
new4 = """        session.flush()
        if execute:
            session.commit()
            print("DECISIONS_COMMITTED (or already were)")
        else:
            print("DRY_RUN: decisions NOT committed by this run (any reused rows were already committed earlier)")

    if not execute:
        print("DRY_RUN: stopping before activation stage. Re-run with --execute to attempt it for real.")
        sys.exit(0)

    with Session(writer_engine) as wsession, wsession.begin():"""
if old4 not in content: raise SystemExit("D_NOT_FOUND")
content = content.replace(old4, new4)

# 5. Remove the now-redundant post-activation rollback block (dead code after sys.exit for dry-run).
old5 = """
    if not execute:
        session.rollback()
        print("DECISIONS_ROLLED_BACK (dry-run, after activation test)")"""
content = content.replace(old5, "")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")
