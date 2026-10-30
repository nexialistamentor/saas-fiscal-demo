"""Focused negative/ABI contract of isolated native builder; does not use Docker."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import b02_g5_native_pg1710_isolated_build as build

V3_HASH="c"*64


def header_fixture(path:Path,policy_hash=V3_HASH):
    path.write_text(
        '/* synthetic test header, never an actual approved root */\n'
        'SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE '
        +policy_hash+'\n',encoding="utf8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativePrebuildContract(unittest.TestCase):
    def test_docker_image_runtime_and_matching_development_headers_guarded(self):
        dockerfile=build.DOCKERFILE
        self.assertIn("FROM postgres:17.10-trixie",dockerfile)
        self.assertNotIn("postgres:17.10-bookworm",dockerfile)
        self.assertIn('test "$VERSION_CODENAME" = "trixie"',dockerfile)
        self.assertIn('pg_config --version',dockerfile)
        self.assertIn('test "$(pg_config --version)" = "PostgreSQL 17.10"',dockerfile)
        self.assertIn('postgresql-server-dev-17',dockerfile)
        self.assertIn('17.10*',dockerfile)
        self.assertIn("readelf -Ws",dockerfile)
        self.assertIn("b02_g5_native_REAL_CLOSED.so",dockerfile)
        self.assertNotIn("B02_G5_TEST_PROFILE",dockerfile)
        self.assertNotIn("docker.sock",dockerfile)

    def test_legacy_root_rejected_even_with_exact_sha(self):
        sha=hashlib.sha256(build.LEGACY_HEADER.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError,"EXPIRED_V1_ROOT_FORBIDDEN"):
            build.check_input(build.LEGACY_HEADER,sha,V3_HASH)

    def test_expired_v2_policy_hash_cannot_be_successor(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"b02_g5_approved_roots.h"
            expired="007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf"
            sha=header_fixture(p,expired)
            with self.assertRaisesRegex(RuntimeError,"EXPIRED_G5_V1_OR_V2_POLICY_FORBIDDEN"):
                build.check_input(p,sha,expired)

    def test_header_must_be_immutable_verified_and_successor_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"b02_g5_approved_roots.h"
            sha=header_fixture(p)
            result=build.check_input(p,sha,V3_HASH)
            self.assertEqual(len(result),2)
            with self.assertRaisesRegex(RuntimeError,"SOURCE_SHA_MISMATCH"):
                build.check_input(p,"0"*64,V3_HASH)
            with self.assertRaisesRegex(RuntimeError,"ROOT_SUBJECT_NOT_SUCCESSOR"):
                build.check_input(p,sha,"f"*64)

    def test_legacy_v1_policy_hash_rejected_inside_other_header(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"b02_g5_approved_roots.h"
            p.write_text("SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE "+V3_HASH
                +" 57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa")
            sha=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError,"ROOT_SUBJECT_NOT_SUCCESSOR"):
                build.check_input(p,sha,V3_HASH)

    def test_no_live_protected_db_mount_or_operation(self):
        src=(ROOT/"tools/b02_g5_native_pg1710_isolated_build.py").read_text()
        self.assertIn('"--network","none"',src)
        self.assertIn("tempfile.TemporaryDirectory",src)
        self.assertIn("docker\",\"image\",\"rm",src.replace(" ",""))
        self.assertNotIn("solveris-pg17-migration-test",src)
        self.assertNotIn("pg_hba.conf",src)
        self.assertNotIn("docker exec",src)
        self.assertNotIn("CREATE FUNCTION",src)
        self.assertNotIn("B02_G5_TEST_PROFILE",src)

    def test_native_build_uses_frozen_verified_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            header=Path(temp)/"b02_g5_approved_roots.h"
            sha=header_fixture(header)
            hashes,images=build.capture_verified_inputs(header,sha,V3_HASH)
            self.assertEqual(set(images),{
                "b02_precommit_guard.c","b02_g5_native_signature.c",
                "b02_g5_approved_roots.h"})
            self.assertEqual(hashlib.sha256(images[header.name]).hexdigest(),sha)
            for p in build.SOURCES:
                self.assertEqual(hashlib.sha256(images[p.name]).hexdigest(),
                                 hashes[str(p.relative_to(ROOT))])
            source=(ROOT/"tools/b02_g5_native_pg1710_isolated_build.py").read_text()
            self.assertIn("source_hashes,snapshot=capture_verified_inputs",source)
            self.assertIn("(tmp/name).write_bytes(data)",source)
            self.assertNotIn("shutil.copyfile",source)

    def test_root_changed_between_verification_and_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            header=Path(temp)/"b02_g5_approved_roots.h"
            sha=header_fixture(header)
            hashes=build.check_input(header,sha,V3_HASH)
            header.write_bytes(b"replaced after original verification")
            with patch.object(build,"check_input",return_value=hashes):
                with self.assertRaisesRegex(RuntimeError,"HEADER_CHANGED_AFTER_VERIFICATION"):
                    build.capture_verified_inputs(header,sha,V3_HASH)

    def test_c_source_changed_between_verification_and_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            header=Path(temp)/"b02_g5_approved_roots.h"
            sha=header_fixture(header)
            hashes=build.check_input(header,sha,V3_HASH)
            original=Path.read_bytes
            first_source=build.SOURCES[0]
            def tampered_read(path):
                return b"tampered C source" if path == first_source else original(path)
            with patch.object(build,"check_input",return_value=hashes):
                with patch.object(Path,"read_bytes",tampered_read):
                    with self.assertRaisesRegex(RuntimeError,"C_SOURCE_CHANGED_AFTER_VERIFICATION"):
                        build.capture_verified_inputs(header,sha,V3_HASH)

    def test_existing_artifact_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"b02_g5_approved_roots.h"
            sha=header_fixture(p)
            out=Path(temp)/"exists.so"
            out.write_bytes(b"EXISTING")
            with self.assertRaisesRegex(RuntimeError,"OUTPUT_ALREADY_EXISTS_PRESERVE"):
                build.build(p,sha,V3_HASH,out)
            self.assertEqual(out.read_bytes(),b"EXISTING")


if __name__=="__main__":
    unittest.main()
