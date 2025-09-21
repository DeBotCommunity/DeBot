from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, BIGINT, TEXT,
    TIMESTAMP, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'
    account_id = Column(Integer, primary_key=True)
    user_telegram_id = Column(BIGINT, unique=True, nullable=True) # Populated after first login
    access_hash = Column(BIGINT, nullable=True) # Populated after first login
    api_id = Column(BYTEA, nullable=False)
    api_hash = Column(BYTEA, nullable=False)
    account_name = Column(String(255), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    lang_code = Column(String(10), default='ru', nullable=False)
    
    # Device info
    device_model = Column(TEXT)
    system_version = Column(TEXT)
    app_version = Column(TEXT)

    # Proxy info
    proxy_type = Column(TEXT)
    proxy_ip = Column(TEXT)
    proxy_port = Column(Integer)
    proxy_username = Column(BYTEA)
    proxy_password = Column(BYTEA)
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    session = relationship("Session", back_populates="account", uselist=False, cascade="all, delete-orphan")
    account_modules = relationship("AccountModule", back_populates="account", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="account")
    module_data = relationship("ModuleData", back_populates="account", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = 'sessions'
    session_id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id', ondelete='CASCADE'), nullable=False, unique=True)
    dc_id = Column(Integer, nullable=False)
    server_address = Column(TEXT)
    port = Column(Integer)
    auth_key_data = Column(BYTEA)
    
    # Update state fields
    pts = Column(Integer)
    qts = Column(Integer)
    date = Column(BIGINT)
    seq = Column(Integer)
    takeout_id = Column(BIGINT)
    
    last_used_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    account = relationship("Account", back_populates="session")

class Module(Base):
    __tablename__ = 'modules'
    module_id = Column(Integer, primary_key=True)
    module_name = Column(String(255), unique=True, nullable=False)
    description = Column(TEXT)
    version = Column(String(50))
    module_path = Column(String(512), nullable=False)
    added_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    account_modules = relationship("AccountModule", back_populates="module", cascade="all, delete-orphan")

class AccountModule(Base):
    __tablename__ = 'account_modules'
    __table_args__ = (UniqueConstraint('account_id', 'module_id', name='_account_module_uc'),)
    
    account_module_id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id', ondelete='CASCADE'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.module_id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    is_trusted = Column(Boolean, default=False)
    configuration = Column(JSONB)
    activated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    account = relationship("Account", back_populates="account_modules")
    module = relationship("Module", back_populates="account_modules")

class Log(Base):
    __tablename__ = 'logs'
    log_id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id', ondelete='SET NULL'))
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    level = Column(String(50), nullable=False)
    message = Column(TEXT, nullable=False)
    module_name = Column(String(255))

    account = relationship("Account", back_populates="logs")

class ModuleData(Base):
    __tablename__ = 'module_data'
    __table_args__ = (UniqueConstraint('account_id', 'module_name', 'data_key', name='_account_module_data_uc'),)

    module_data_id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id', ondelete='CASCADE'), nullable=False)
    module_name = Column(String(255), nullable=False)
    data_key = Column(String(255), nullable=False)
    data_value = Column(BYTEA, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    account = relationship("Account", back_populates="module_data")
