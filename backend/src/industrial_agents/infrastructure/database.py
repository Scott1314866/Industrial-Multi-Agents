from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from industrial_agents.domain.models import GraphRequest, GraphResponse, Role, RunStatus
from industrial_agents.domain.security import hash_password, verify_password


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    machine_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    machine_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(Text)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuditRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def setup(self, *, seed_demo: bool = False) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if seed_demo:
            await self.seed()

    async def close(self) -> None:
        await self.engine.dispose()

    async def seed(self) -> None:
        async with self.sessions() as session:
            existing = await session.scalar(select(UserRow.id).limit(1))
            if existing:
                return
            tenant = "tenant-moldwise-demo"
            users = [
                ("engineer@moldwise.local", "凌工", Role.ENGINEER, "Engineer123!"),
                ("customer@moldwise.local", "示范客户", Role.CUSTOMER, "Customer123!"),
                ("admin@moldwise.local", "平台管理员", Role.ADMIN, "Admin123!"),
            ]
            session.add_all(
                [
                    UserRow(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant,
                        email=email,
                        display_name=name,
                        role=role.value,
                        password_hash=hash_password(password),
                    )
                    for email, name, role, password in users
                ]
            )
            await session.commit()


class Repository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def authenticate(self, email: str, password: str) -> UserRow | None:
        async with self.sessions() as session:
            user = await session.scalar(select(UserRow).where(UserRow.email == email.lower()))
            if not user or not user.active or not verify_password(password, user.password_hash):
                return None
            return user

    async def get_user(self, user_id: str) -> UserRow | None:
        async with self.sessions() as session:
            return await session.get(UserRow, user_id)

    async def create_conversation(
        self, *, tenant_id: str, user_id: str, machine_id: str, title: str
    ) -> ConversationRow:
        row = ConversationRow(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            machine_id=machine_id,
            title=title[:200],
        )
        async with self.sessions() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def list_conversations(self, tenant_id: str, user_id: str, is_admin: bool) -> list[ConversationRow]:
        async with self.sessions() as session:
            query = select(ConversationRow).where(ConversationRow.tenant_id == tenant_id)
            if not is_admin:
                query = query.where(ConversationRow.user_id == user_id)
            result = await session.scalars(query.order_by(ConversationRow.updated_at.desc()).limit(100))
            return list(result)

    async def get_conversation(self, conversation_id: str, tenant_id: str) -> ConversationRow | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(ConversationRow).where(
                    ConversationRow.id == conversation_id,
                    ConversationRow.tenant_id == tenant_id,
                )
            )

    async def create_run(self, conversation_id: str, request: GraphRequest) -> RunRow:
        row = RunRow(
            id=request.run_id,
            conversation_id=conversation_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            machine_id=request.machine_id,
            status=RunStatus.QUEUED.value,
            query=request.query,
            request_payload=request.model_dump(mode="json"),
        )
        async with self.sessions() as session:
            session.add(row)
            conversation = await session.get(ConversationRow, conversation_id)
            if conversation:
                conversation.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
        return row

    async def get_run(self, run_id: str, tenant_id: str | None = None) -> RunRow | None:
        async with self.sessions() as session:
            query = select(RunRow).where(RunRow.id == run_id)
            if tenant_id:
                query = query.where(RunRow.tenant_id == tenant_id)
            return await session.scalar(query)

    async def list_runs(self, tenant_id: str, user_id: str, is_admin: bool) -> list[RunRow]:
        async with self.sessions() as session:
            query = select(RunRow).where(RunRow.tenant_id == tenant_id)
            if not is_admin:
                query = query.where(RunRow.user_id == user_id)
            result = await session.scalars(query.order_by(RunRow.created_at.desc()).limit(100))
            return list(result)

    async def update_run(
        self,
        run_id: str,
        status: RunStatus,
        result: GraphResponse | None = None,
        error: str | None = None,
    ) -> None:
        async with self.sessions() as session:
            row = await session.get(RunRow, run_id)
            if not row:
                return
            row.status = status.value
            row.result_payload = result.model_dump(mode="json") if result else row.result_payload
            row.error_message = error
            row.updated_at = datetime.now(UTC)
            await session.commit()

    async def audit(
        self,
        *,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        async with self.sessions() as session:
            session.add(
                AuditRow(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail or {},
                )
            )
            await session.commit()
