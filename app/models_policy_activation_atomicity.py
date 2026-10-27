"""Prospective policy-only atomicity metadata. Import does not execute DDL.
No edits to app/models.py, 0062 or normative generation/outbox entities.
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, CheckConstraint, ForeignKeyConstraint, UniqueConstraint, FetchedValue
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.models import Base, PolicyActivationExecution, PolicyActivation, PolicyDecision

def _json():return JSON().with_variant(JSONB(), 'postgresql')

# Register prospective metadata only when this new module is explicitly used.
for table in (PolicyActivationExecution.__table__,PolicyActivation.__table__):
    table.append_column(Column('b02_policy_txid',Text,nullable=True,server_default=FetchedValue()))
    table.append_column(Column('policy_decision_record_hash',String(64),nullable=True))
PolicyActivation.__table__.append_column(Column('policy_activation_execution_record_hash',String(64),nullable=True))
Base.metadata.tables['policy_decisions'].append_constraint(UniqueConstraint('decision_id','record_hash','policy_id','policy_version','policy_hash',name='uq_b02p_decision_exact'))
Base.metadata.tables['policy_activation_executions'].append_constraint(UniqueConstraint('policy_activation_execution_id','record_hash','policy_decision_id','policy_decision_record_hash','policy_id','policy_version','policy_hash',name='uq_b02p_exec_exact'))
Base.metadata.tables['policy_activations'].append_constraint(UniqueConstraint('policy_activation_id','record_hash','policy_activation_execution_id','policy_activation_execution_record_hash','policy_decision_id','policy_decision_record_hash','policy_id','policy_version','policy_hash',name='uq_b02p_activation_exact'))
Base.metadata.tables['policy_activation_executions'].append_constraint(ForeignKeyConstraint(['policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_decisions.decision_id', 'policy_decisions.record_hash', 'policy_decisions.policy_id', 'policy_decisions.policy_version', 'policy_decisions.policy_hash'],name='fk_b02p_exec_decision',ondelete='RESTRICT'))
Base.metadata.tables['policy_activations'].append_constraint(ForeignKeyConstraint(['policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_executions.policy_activation_execution_id', 'policy_activation_executions.record_hash', 'policy_activation_executions.policy_decision_id', 'policy_activation_executions.policy_decision_record_hash', 'policy_activation_executions.policy_id', 'policy_activation_executions.policy_version', 'policy_activation_executions.policy_hash'],name='fk_b02p_activation_exec',ondelete='RESTRICT'))

class PolicyActivationGeneration(Base):
    __tablename__='policy_activation_generations'
    __table_args__=(
        UniqueConstraint('policy_activation_generation_id','record_hash',name='uq_b02p_0_0'),
        UniqueConstraint('policy_activation_execution_id',name='uq_b02p_0_1'),
        UniqueConstraint('policy_activation_id',name='uq_b02p_0_2'),
        UniqueConstraint('record_hash',name='uq_b02p_0_3'),
        UniqueConstraint('policy_activation_generation_id','policy_activation_id','policy_activation_record_hash',name='uq_b02p_0_4'),
        UniqueConstraint('policy_activation_generation_id','record_hash','policy_activation_id','policy_activation_record_hash','policy_activation_execution_id','policy_activation_execution_record_hash','policy_decision_id','policy_decision_record_hash','policy_id','policy_version','policy_hash',name='uq_b02p_0_5'),
        ForeignKeyConstraint(['policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_executions.policy_activation_execution_id', 'policy_activation_executions.record_hash', 'policy_activation_executions.policy_decision_id', 'policy_activation_executions.policy_decision_record_hash', 'policy_activation_executions.policy_id', 'policy_activation_executions.policy_version', 'policy_activation_executions.policy_hash'],name='fk_b02p_0_0',ondelete='RESTRICT'),
        ForeignKeyConstraint(['policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activations.policy_activation_id', 'policy_activations.record_hash', 'policy_activations.policy_activation_execution_id', 'policy_activations.policy_activation_execution_record_hash', 'policy_activations.policy_decision_id', 'policy_activations.policy_decision_record_hash', 'policy_activations.policy_id', 'policy_activations.policy_version', 'policy_activations.policy_hash'],name='fk_b02p_0_1',ondelete='RESTRICT'),
        CheckConstraint('schema_version=1',name='ck_b02p_0_0'),
        CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'",name='ck_b02p_0_1'),
        CheckConstraint('policy_version>0',name='ck_b02p_0_2'),
        CheckConstraint("policy_activation_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_3'),
        CheckConstraint("policy_activation_execution_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_4'),
        CheckConstraint("policy_decision_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_5'),
        CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_6'),
        CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_7'),
        CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_8'),
        CheckConstraint('is_complete',name='ck_b02p_0_9'),
        CheckConstraint("jsonb_typeof(completion_manifest)='object'",name='ck_b02p_0_10'),
        CheckConstraint("jsonb_typeof(provenance)='object'",name='ck_b02p_0_11'),
    )
    policy_activation_generation_id=Column(String(64),nullable=False,primary_key=True)
    policy_activation_id=Column(String(64),nullable=False)
    policy_activation_record_hash=Column(String(64),nullable=False)
    policy_activation_execution_id=Column(String(64),nullable=False)
    policy_activation_execution_record_hash=Column(String(64),nullable=False)
    policy_decision_id=Column(String(64),nullable=False)
    policy_decision_record_hash=Column(String(64),nullable=False)
    policy_id=Column(String(64),nullable=False)
    policy_version=Column(Integer(),nullable=False)
    policy_hash=Column(String(64),nullable=False)
    schema_version=Column(Integer(),nullable=False)
    domain=Column(String(255),nullable=False)
    modality=Column(String(64),nullable=False)
    scope_descriptor=Column(_json(),nullable=False)
    scope_hash=Column(String(64),nullable=False)
    operational_interval=Column(_json(),nullable=False)
    completion_manifest=Column(_json(),nullable=False)
    is_complete=Column(Boolean(),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False)
    provenance=Column(_json(),nullable=False)
    assigned_txid=Column(Text(),nullable=False,server_default=FetchedValue())
    record_hash=Column(String(64),nullable=False,server_default=FetchedValue())

class PolicyActivationOutboxEvent(Base):
    __tablename__='policy_activation_outbox_events'
    __table_args__=(
        UniqueConstraint('policy_activation_outbox_event_id','record_hash',name='uq_b02p_1_0'),
        UniqueConstraint('policy_activation_execution_id',name='uq_b02p_1_1'),
        UniqueConstraint('policy_activation_id',name='uq_b02p_1_2'),
        UniqueConstraint('policy_activation_generation_id',name='uq_b02p_1_3'),
        UniqueConstraint('record_hash',name='uq_b02p_1_4'),
        ForeignKeyConstraint(['policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_executions.policy_activation_execution_id', 'policy_activation_executions.record_hash', 'policy_activation_executions.policy_decision_id', 'policy_activation_executions.policy_decision_record_hash', 'policy_activation_executions.policy_id', 'policy_activation_executions.policy_version', 'policy_activation_executions.policy_hash'],name='fk_b02p_1_0',ondelete='RESTRICT'),
        ForeignKeyConstraint(['policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activations.policy_activation_id', 'policy_activations.record_hash', 'policy_activations.policy_activation_execution_id', 'policy_activations.policy_activation_execution_record_hash', 'policy_activations.policy_decision_id', 'policy_activations.policy_decision_record_hash', 'policy_activations.policy_id', 'policy_activations.policy_version', 'policy_activations.policy_hash'],name='fk_b02p_1_1',ondelete='RESTRICT'),
        ForeignKeyConstraint(['policy_activation_generation_id', 'policy_activation_generation_hash', 'policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_generations.policy_activation_generation_id', 'policy_activation_generations.record_hash', 'policy_activation_generations.policy_activation_id', 'policy_activation_generations.policy_activation_record_hash', 'policy_activation_generations.policy_activation_execution_id', 'policy_activation_generations.policy_activation_execution_record_hash', 'policy_activation_generations.policy_decision_id', 'policy_activation_generations.policy_decision_record_hash', 'policy_activation_generations.policy_id', 'policy_activation_generations.policy_version', 'policy_activation_generations.policy_hash'],name='fk_b02p_1_2',ondelete='RESTRICT'),
        CheckConstraint('schema_version=1',name='ck_b02p_1_0'),
        CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'",name='ck_b02p_1_1'),
        CheckConstraint('policy_version>0',name='ck_b02p_1_2'),
        CheckConstraint("policy_activation_generation_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_3'),
        CheckConstraint("policy_activation_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_4'),
        CheckConstraint("policy_activation_execution_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_5'),
        CheckConstraint("policy_decision_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_6'),
        CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_7'),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_8'),
        CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_9'),
        CheckConstraint("event_type='policy_activation_completed'",name='ck_b02p_1_10'),
        CheckConstraint("jsonb_typeof(payload)='object'",name='ck_b02p_1_11'),
        CheckConstraint("jsonb_typeof(provenance)='object'",name='ck_b02p_1_12'),
    )
    policy_activation_outbox_event_id=Column(String(64),nullable=False,primary_key=True)
    policy_activation_generation_id=Column(String(64),nullable=False)
    policy_activation_generation_hash=Column(String(64),nullable=False)
    policy_activation_id=Column(String(64),nullable=False)
    policy_activation_record_hash=Column(String(64),nullable=False)
    policy_activation_execution_id=Column(String(64),nullable=False)
    policy_activation_execution_record_hash=Column(String(64),nullable=False)
    policy_decision_id=Column(String(64),nullable=False)
    policy_decision_record_hash=Column(String(64),nullable=False)
    policy_id=Column(String(64),nullable=False)
    policy_version=Column(Integer(),nullable=False)
    policy_hash=Column(String(64),nullable=False)
    schema_version=Column(Integer(),nullable=False)
    event_type=Column(String(64),nullable=False)
    payload=Column(_json(),nullable=False,server_default=FetchedValue())
    payload_hash=Column(String(64),nullable=False,server_default=FetchedValue())
    created_at=Column(DateTime(timezone=True),nullable=False)
    provenance=Column(_json(),nullable=False)
    assigned_txid=Column(Text(),nullable=False,server_default=FetchedValue())
    record_hash=Column(String(64),nullable=False,server_default=FetchedValue())

PolicyActivation.__table__.append_constraint(ForeignKeyConstraint(['activation_generation_id', 'policy_activation_id', 'record_hash'],['policy_activation_generations.policy_activation_generation_id', 'policy_activation_generations.policy_activation_id', 'policy_activation_generations.policy_activation_record_hash'],name='fk_b02p_activation_generation',deferrable=True,initially='DEFERRED',use_alter=True,ondelete='RESTRICT'))

# Reuse the original ORM mutation guard; DB triggers remain authoritative.
from sqlalchemy import event as _policy_event
from app.models import _adr020_reject_append_only_mutation as _policy_reject_mutation
for _entity in (PolicyActivationGeneration,PolicyActivationOutboxEvent):
    _policy_event.listen(_entity,'before_update',_policy_reject_mutation)
    _policy_event.listen(_entity,'before_delete',_policy_reject_mutation)
