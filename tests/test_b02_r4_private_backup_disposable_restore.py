"""R4 security/cleanup contracts. Synthetic only, does not touch Docker."""
import contextlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import b02_r4_private_backup_disposable_restore as r4


class R4PrivateRestoreTests(unittest.TestCase):
    def test_source_reader_uses_existing_role_and_whitelisted_tables(self):
        expected={name:0 for name in r4.TABLES}
        with patch.object(r4.owner,"psql",return_value=[
            "BEGIN",r4.bridge.DATABASE+"|"+r4.ROLE,
            json.dumps(expected),"ROLLBACK"
        ]) as psql:
            self.assertEqual(r4.snapshot(r4.ROLE),expected)
        statement=psql.call_args.args[0]
        self.assertIn("BEGIN READ ONLY;",statement)
        self.assertIn("ROLLBACK;",statement)
        self.assertNotIn("INSERT ",statement)
        self.assertNotIn("GRANT ",statement)
        self.assertEqual(psql.call_args.args[1],r4.ROLE)

    def test_unapproved_snapshot_identity_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"SNAPSHOT_ROLE"):
            r4.snapshot("postgres")
        with patch.object(r4.owner,"psql",return_value=[
            "BEGIN","wrong-db|solveris_test","{}","ROLLBACK"
        ]):
            with self.assertRaisesRegex(RuntimeError,"SOURCE_SNAPSHOT_IDENTITY"):
                r4.snapshot(r4.ROLE)

    def test_private_ntfs_guard_fails_off_windows(self):
        with patch.object(r4,"os",SimpleNamespace(name="posix")):
            with self.assertRaisesRegex(RuntimeError,"NTFS_WINDOWS"):
                r4.verify_private_directory(Path(tempfile.gettempdir())/"never-create","0"*32)

    def test_disposable_image_not_unpinned(self):
        with self.assertRaisesRegex(RuntimeError,"SOURCE_IMAGE_UNPINNED"):
            r4.disposable_restore(Path("not-a-dump"),"postgres:latest","0"*32)

    def test_disposable_uses_no_network_and_single_transaction_and_cleans(self):
        image="sha256:"+"a"*64
        output=json.dumps({name:0 for name in r4.TABLES})
        with patch.object(r4,"invoke",side_effect=["created", "", "", "", output]) as cmd, \
             patch.object(r4,"wait_ready"), \
             patch.object(r4.subprocess,"run",return_value=MagicMock(returncode=0)) as sub:
            result=r4.disposable_restore(Path("protected.dump"),image,"a"*32)
        self.assertEqual(result["network"],"none")
        self.assertFalse(result["installed_to_protected"])
        commands=[x.args[0] for x in cmd.call_args_list]
        self.assertIn("--network",commands[0])
        self.assertIn("none",commands[0])
        self.assertNotIn("-p",commands[0])
        self.assertNotIn("-v",commands[0])
        self.assertIn("--single-transaction",commands[3])
        self.assertIn("--no-owner",commands[3])
        self.assertIn("--no-acl",commands[3])
        self.assertEqual(sub.call_args.args[0][:4],["docker","rm","-f","-v"])
        self.assertIn("disposable",sub.call_args.args[0][-1])

    def test_pg_restore_toc_consumes_stdin_without_dash_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/"protected_pg1710.dump"
            archive.write_bytes(b"PGDMP"+b"synthetic")
            p=MagicMock(returncode=0,stdout=b"; TOC Entries: 3\\n",stderr=b"")
            with patch.object(r4.subprocess,"run",return_value=p) as call:
                result=r4.inspect_private_archive(archive)
        self.assertEqual(call.call_args.args[0][-2:],["pg_restore","--list"])
        self.assertNotIn("-",call.call_args.args[0][-2:])
        self.assertEqual(result["backup_bytes"],len(b"PGDMPsynthetic"))
        self.assertEqual(len(result["toc_sha256"]),64)

    def test_existing_backup_rejects_non_custom_header_without_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/"protected_pg1710.dump"
            archive.write_bytes(b"not-an-archive")
            with patch.object(r4.subprocess,"run") as call:
                with self.assertRaisesRegex(RuntimeError,"PRIVATE_ARCHIVE_NOT_CUSTOM_FORMAT"):
                    r4.inspect_private_archive(archive)
                call.assert_not_called()

    def test_backup_command_streams_without_password_or_host_network(self):
        src=(ROOT/"tools/b02_r4_private_backup_disposable_restore.py").read_text(
            encoding="utf8")
        self.assertIn('"--no-password"',src)
        self.assertIn('"--format=custom"',src)
        self.assertIn('"--lock-wait-timeout=10000"',src)
        self.assertIn('path.open("xb")',src)
        self.assertIn('source_count_snapshot',src)
        self.assertIn("NOT_FULL_R4_ACL_OR_NATIVE_OR_CAS_APPROVAL",src)
        for risky in ("docker system prune","docker volume rm","pg_restore -d solveris_b02_r4g_test",
                      "ALTER ROLE","GRANT ALL"):
            self.assertNotIn(risky,src)
        self.assertIn(r4.PATH,r4.bridge.ALLOWED)


if __name__=="__main__":
    unittest.main()
