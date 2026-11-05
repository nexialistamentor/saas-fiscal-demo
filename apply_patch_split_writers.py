path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = 'os.environ["DATABASE_URL"] = "postgresql+psycopg2://solveris_b02_policy_writer:solveris_policy_writer_local@localhost:55432/solveris_b02_r4g_test"'
new = ('DSN_OWNER = "postgresql+psycopg2://solveris_test:solveris_test@localhost:55432/solveris_b02_r4g_test"\n'
       'DSN_POLICY_WRITER = "postgresql+psycopg2://solveris_b02_policy_writer:solveris_policy_writer_local@localhost:55432/solveris_b02_r4g_test"')
if old not in content:
    raise SystemExit("A_NOT_FOUND")
content = content.replace(old, new)

old2 = '''if __name__ == "__main__":
    engine = create_engine(os.environ["DATABASE_URL"])
    execute = "--execute" in sys.argv
    run(engine, execute)'''
new2 = '''if __name__ == "__main__":
    owner_engine = create_engine(DSN_OWNER)
    writer_engine = create_engine(DSN_POLICY_WRITER)
    execute = "--execute" in sys.argv
    run(owner_engine, writer_engine, execute)'''
if old2 not in content:
    raise SystemExit("B_NOT_FOUND")
content = content.replace(old2, new2)

old3 = "def run(engine, execute: bool):\n    with Session(engine) as session, session.begin():\n        conn = session.connection()"
new3 = "def run(owner_engine, writer_engine, execute: bool):\n    with Session(owner_engine) as session, session.begin():\n        conn = session.connection()"
if old3 not in content:
    raise SystemExit("C_NOT_FOUND")
content = content.replace(old3, new3)

old4 = '''        result = stage_policy_activation(
            conn, execution=execution, activation=activation,
            generation_id="B02-389cce04-generation-v1",
            outbox_id="B02-389cce04-outbox-v1",
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
        )
        print("ACTIVATION_RESULT =", result)

        if execute:
            session.commit()
            print("COMMITTED")
        else:
            session.rollback()
            print("ROLLED_BACK (dry-run)")'''
new4 = '''        if execute:
            session.commit()
            print("DECISIONS_COMMITTED")
        else:
            session.rollback()
            print("DECISIONS_ROLLED_BACK (dry-run) -- activation stage skipped in dry-run")
            return

    with Session(writer_engine) as wsession, wsession.begin():
        wconn = wsession.connection()
        result = stage_policy_activation(
            wconn, execution=execution, activation=activation,
            generation_id="B02-389cce04-generation-v1",
            outbox_id="B02-389cce04-outbox-v1",
            provenance={"source": "SOLVERIS_B02_G5_R1_MATERIALIZATION", "synthetic_only": False},
        )
        print("ACTIVATION_RESULT =", result)
        if execute:
            wsession.commit()
            print("ACTIVATION_COMMITTED")
        else:
            wsession.rollback()
            print("ACTIVATION_ROLLED_BACK (dry-run)")'''
if old4 not in content:
    raise SystemExit("D_NOT_FOUND")
content = content.replace(old4, new4)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")
