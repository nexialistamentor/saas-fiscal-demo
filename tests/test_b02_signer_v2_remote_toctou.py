"""B02 PR28 focal source reconsult and clock-after-remote gates (synthetic)."""
import importlib.util
import json
from datetime import datetime as RealDatetime, timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, BestAvailableEncryption, PrivateFormat

SOURCE=Path(__file__).resolve().parents[1]/'tools/b02_documentary_signer_v2.py'
spec=importlib.util.spec_from_file_location('signer_recheck_under_test', SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
START=RealDatetime(2026,11,3,18,tzinfo=timezone.utc)
END=RealDatetime(2026,11,4,18,tzinfo=timezone.utc)


def make_case(tmp_path, monkeypatch):
    key=Ed25519PrivateKey.generate()
    der=key.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)
    pem=key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,BestAvailableEncryption(b'synthetic-only'))
    private=tmp_path/'private.pem';private.write_bytes(pem)
    root=tmp_path/'bundle';root.mkdir()
    act=tmp_path/'authority.json'
    decision={'valid_from':'2026-11-03T18:00:00Z','valid_until':'2026-11-04T18:00:00Z'}
    raw=json.dumps(decision).encode()
    blob=s.git_blob(SOURCE.read_bytes())
    adoption={'signer_source_git_blob':blob,'decision_sha256':s.APPROVED_DECISION_SHA256,
              'signing_authorized':True}
    act.write_text(json.dumps(adoption))
    writes=[]
    legacy=SimpleNamespace(parse=lambda b:json.loads(b),write_new=lambda target,buf:writes.append((target,buf)))
    result={'root':root,'legacy':legacy,'decision_raw':raw,
            'public':key.public_key(),'der':der,'signer_source_git_blob':blob}
    monkeypatch.setattr(s,'validate',lambda args,**kwargs: result)
    monkeypatch.setattr(s,'_source_pinned_signer_authority',lambda x,y: s.sha(x))
    monkeypatch.setattr(s,'getpass',SimpleNamespace(getpass=lambda prompt:'synthetic-only'))
    auth={'bytes':b'original GitHub act'}
    monkeypatch.setattr(s,'_original_authorization',lambda decision: auth['bytes'])
    args=SimpleNamespace(private=str(private),signer_authority=str(act),authorization=None,
                         authorization_sha256=None)
    return args,writes,auth


def test_toctou_authorization_changes_during_password_no_signature_persisted(tmp_path,monkeypatch):
    args,writes,auth=make_case(tmp_path,monkeypatch)
    def delay(prompt):
        auth['bytes']=b'changed during password wait'
        return 'synthetic-only'
    monkeypatch.setattr(s,'getpass',SimpleNamespace(getpass=delay))
    with pytest.raises(ValueError,match='ORIGINAL_AUTHORIZATION_CHANGED_AFTER_PASSWORD'):
        s.sign(args)
    assert writes==[]
    assert not (tmp_path/'bundle'/'signature.bin').exists()


def test_toctou_window_expires_during_pre_sign_remote_no_signature_persisted(tmp_path,monkeypatch):
    args,writes,auth=make_case(tmp_path,monkeypatch)
    remote={'done':False}
    def slow_origin(_):
        remote['done']=True
        return auth['bytes']
    monkeypatch.setattr(s,'_original_authorization',slow_origin)
    class Clock(RealDatetime):
        @classmethod
        def now(cls,tz=None):
            return RealDatetime(2026,11,4,18,0,1,tzinfo=timezone.utc) if remote['done'] else RealDatetime(2026,11,4,17,59,59,tzinfo=timezone.utc)
    monkeypatch.setattr(s,'datetime',Clock)
    with pytest.raises(ValueError,match='SIGNING_WINDOW_CLOSED'):
        s.sign(args)
    assert writes==[]
    assert not (tmp_path/'bundle'/'signature.bin').exists()


def test_toctou_window_expires_during_pre_persist_remote_no_signature_persisted(tmp_path,monkeypatch):
    args,writes,auth=make_case(tmp_path,monkeypatch)
    call={'n':0}
    def source(_):
        call['n']+=1
        return auth['bytes']
    monkeypatch.setattr(s,'_original_authorization',source)
    class Clock(RealDatetime):
        @classmethod
        def now(cls,tz=None):
            return (RealDatetime(2026,11,4,18,0,1,tzinfo=timezone.utc) if call['n']>=3
                    else RealDatetime(2026,11,4,17,59,59,tzinfo=timezone.utc))
    monkeypatch.setattr(s,'datetime',Clock)
    with pytest.raises(ValueError,match='SIGNING_WINDOW_CLOSED_BEFORE_PERSIST'):
        s.sign(args)
    assert call['n']>=3
    assert writes==[]
    assert not (tmp_path/'bundle'/'signature.bin').exists()
