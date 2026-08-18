from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from industrial_agents.domain.models import GraphRequest, GraphResponse, Role, RunStatus
from industrial_agents.domain.security import hash_password, verify_password


class Base(DeclarativeBase):
    pass


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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


class UserMachineGrantRow(Base):
    __tablename__ = "user_machine_grants"
    __table_args__ = (UniqueConstraint("user_id", "machine_id", name="uq_user_machine_grant"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    machine_id: Mapped[str] = mapped_column(String(64), index=True)
    granted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


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
        if seed_demo:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await self.seed()
            return
        async with self.sessions() as session:
            await session.execute(select(1))

    async def close(self) -> None:
        await self.engine.dispose()

    async def seed(self) -> None:
        async with self.sessions() as session:
            tenant = "tenant-moldwise-demo"
            users = [
                ("engineer@moldwise.local", "凌工", Role.ENGINEER, "Engineer123!"),
                ("customer@moldwise.local", "示范客户", Role.CUSTOMER, "Customer123!"),
                ("admin@moldwise.local", "平台管理员", Role.ADMIN, "Admin123!"),
            ]
            demo_users: list[UserRow] = []
            for email, name, role, password in users:
                user = await session.scalar(select(UserRow).where(UserRow.email == email))
                if not user:
                    user = UserRow(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant,
                        email=email,
                        display_name=name,
                        role=role.value,
                        password_hash=hash_password(password),
                    )
                    session.add(user)
                demo_users.append(user)
            await session.flush()
            machine_ids = ("IMM-240A", "IMM-320B", "IMM-450C", "IMM-550D")
            for user in demo_users:
                for machine_id in machine_ids:
                    existing = await session.scalar(
                        select(UserMachineGrantRow.id).where(
                            UserMachineGrantRow.user_id == user.id,
                            UserMachineGrantRow.machine_id == machine_id,
                        )
                    )
                    if not existing:
                        session.add(
                            UserMachineGrantRow(
                                id=str(uuid.uuid4()),
                                user_id=user.id,
                                machine_id=machine_id,
                                granted_by=None,
                            )
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

    async def get_user_by_email(self, email: str) -> UserRow | None:
        async with self.sessions() as session:
            return cast(UserRow | None, await session.scalar(select(UserRow).where(UserRow.email == email.lower())))

    async def create_user(
        self, *, tenant_id: str, email: str, display_name: str, role: Role, password: str
    ) -> UserRow:
        row = UserRow(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email=email.lower(),
            display_name=display_name,
            role=role.value,
            password_hash=hash_password(password),
        )
        async with self.sessions() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def tenant_has_admin(self, tenant_id: str) -> bool:
        async with self.sessions() as session:
            admin_id = await session.scalar(
                select(UserRow.id).where(UserRow.tenant_id == tenant_id, UserRow.role == Role.ADMIN.value).limit(1)
            )
            return admin_id is not None

    async def grant_machine(self, user_id: str, machine_id: str, granted_by: str | None = None) -> bool:
        async with self.sessions() as session:
            existing = await session.scalar(
                select(UserMachineGrantRow.id).where(
                    UserMachineGrantRow.user_id == user_id,
                    UserMachineGrantRow.machine_id == machine_id,
                )
            )
            if existing:
                return False
            session.add(
                UserMachineGrantRow(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    machine_id=machine_id,
                    granted_by=granted_by,
                )
            )
            await session.commit()
            return True

    async def revoke_machine(self, user_id: str, machine_id: str) -> bool:
        async with self.sessions() as session:
            row = await session.scalar(
                select(UserMachineGrantRow).where(
                    UserMachineGrantRow.user_id == user_id,
                    UserMachineGrantRow.machine_id == machine_id,
                )
            )
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def list_machine_grants(self, user_id: str) -> set[str]:
        async with self.sessions() as session:
            result = await session.scalars(
                select(UserMachineGrantRow.machine_id).where(UserMachineGrantRow.user_id == user_id)
            )
            return set(result)

    async def has_machine_grant(self, user_id: str, machine_id: str) -> bool:
        async with self.sessions() as session:
            grant = await session.scalar(
                select(UserMachineGrantRow.id).where(
                    UserMachineGrantRow.user_id == user_id,
                    UserMachineGrantRow.machine_id == machine_id,
                )
            )
            return grant is not None

    async def create_auth_session(
        self,
        *,
        session_id: str,
        user_id: str,
        token_id: str,
        token_digest: str,
        expires_at: datetime,
    ) -> AuthSessionRow:
        now = datetime.now(UTC)
        auth_session = AuthSessionRow(
            id=session_id,
            user_id=user_id,
            created_at=now,
            last_seen_at=now,
            expires_at=expires_at,
        )
        refresh_token = RefreshTokenRow(
            id=token_id,
            session_id=session_id,
            token_digest=token_digest,
            created_at=now,
            expires_at=expires_at,
        )
        async with self.sessions() as session:
            session.add_all([auth_session, refresh_token])
            await session.commit()
            await session.refresh(auth_session)
        return auth_session

    async def rotate_refresh_token(
        self,
        *,
        session_id: str,
        old_digest: str,
        new_token_id: str,
        new_digest: str,
        expires_at: datetime,
    ) -> str:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            auth_session = await session.scalar(
                select(AuthSessionRow).where(AuthSessionRow.id == session_id).with_for_update()
            )
            token = await session.scalar(
                select(RefreshTokenRow)
                .where(RefreshTokenRow.token_digest == old_digest, RefreshTokenRow.session_id == session_id)
                .with_for_update()
            )
            if not auth_session or not token:
                return "invalid"
            if auth_session.revoked_at or _utc(auth_session.expires_at) <= now:
                return "invalid"
            if token.consumed_at or token.revoked_at or _utc(token.expires_at) <= now:
                auth_session.revoked_at = now
                await session.execute(
                    update(RefreshTokenRow)
                    .where(RefreshTokenRow.session_id == session_id, RefreshTokenRow.revoked_at.is_(None))
                    .values(revoked_at=now)
                )
                await session.commit()
                return "reused"
            token.consumed_at = now
            token.replaced_by_id = new_token_id
            auth_session.last_seen_at = now
            auth_session.expires_at = expires_at
            session.add(
                RefreshTokenRow(
                    id=new_token_id,
                    session_id=session_id,
                    token_digest=new_digest,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            await session.commit()
            return "rotated"

    async def get_active_session(self, session_id: str, user_id: str) -> AuthSessionRow | None:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            return cast(
                AuthSessionRow | None,
                await session.scalar(
                    select(AuthSessionRow).where(
                        AuthSessionRow.id == session_id,
                        AuthSessionRow.user_id == user_id,
                        AuthSessionRow.revoked_at.is_(None),
                        AuthSessionRow.expires_at > now,
                    )
                ),
            )

    async def list_auth_sessions(self, user_id: str) -> list[AuthSessionRow]:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            rows = await session.scalars(
                select(AuthSessionRow)
                .where(
                    AuthSessionRow.user_id == user_id,
                    AuthSessionRow.revoked_at.is_(None),
                    AuthSessionRow.expires_at > now,
                )
                .order_by(AuthSessionRow.last_seen_at.desc())
            )
            return list(rows)

    async def revoke_auth_session(self, session_id: str, user_id: str | None = None) -> bool:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            query = select(AuthSessionRow).where(AuthSessionRow.id == session_id)
            if user_id:
                query = query.where(AuthSessionRow.user_id == user_id)
            row = await session.scalar(query.with_for_update())
            if not row:
                return False
            if not row.revoked_at:
                row.revoked_at = now
                await session.execute(
                    update(RefreshTokenRow)
                    .where(RefreshTokenRow.session_id == row.id, RefreshTokenRow.revoked_at.is_(None))
                    .values(revoked_at=now)
                )
                await session.commit()
            return True

    async def revoke_auth_session_by_digest(self, token_digest: str) -> bool:
        async with self.sessions() as session:
            token = await session.scalar(select(RefreshTokenRow).where(RefreshTokenRow.token_digest == token_digest))
        if not token:
            return False
        return await self.revoke_auth_session(token.session_id)

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
            return cast(
                ConversationRow | None,
                await session.scalar(
                    select(ConversationRow).where(
                        ConversationRow.id == conversation_id,
                        ConversationRow.tenant_id == tenant_id,
                    )
                ),
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
            return cast(RunRow | None, await session.scalar(query))

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
