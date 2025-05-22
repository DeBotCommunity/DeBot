import asyncpg
import logging
import os
import json # Added for module_data serialization
from typing import Optional, Any # Added Any for module_data value type
from userbot.src.encrypt import encryption_manager

# Default connection parameters - these should ideally be loaded from environment variables or a config file.
DEFAULT_DB_HOST = os.getenv("DB_HOST", "localhost")
DEFAULT_DB_PORT = int(os.getenv("DB_PORT", 5432))
DEFAULT_DB_USER = os.getenv("DB_USER", "userbot")
DEFAULT_DB_PASS = os.getenv("DB_PASS", "userbot_password") # Use a default password
DEFAULT_DB_NAME = os.getenv("DB_NAME", "userbot_db")

DB_POOL = None

logger = logging.getLogger(__name__)
# Configure basic logging if not already configured by the application
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def get_db_pool(
    db_host=DEFAULT_DB_HOST,
    db_port=DEFAULT_DB_PORT,
    db_user=DEFAULT_DB_USER,
    db_pass=DEFAULT_DB_PASS,
    db_name=DEFAULT_DB_NAME,
):
    global DB_POOL
    if DB_POOL is None:
        try:
            logger.info(f"Attempting to create database connection pool for db: {db_name} on {db_host}:{db_port} with user: {db_user}")
            DB_POOL = await asyncpg.create_pool(
                user=db_user,
                password=db_pass,
                database=db_name,
                host=db_host,
                port=db_port,
                min_size=1,
                max_size=10
            )
            logger.info("Successfully created database connection pool.")
        except Exception as e:
            logger.error(f"Error creating database connection pool: {e}")
            DB_POOL = None # Ensure pool is None if creation fails
            raise
    return DB_POOL

async def close_db_pool():
    global DB_POOL
    if DB_POOL:
        await DB_POOL.close()
        DB_POOL = None
        logger.info("Database connection pool closed.")


async def initialize_database():
    pool = await get_db_pool()
    if not pool:
        logger.error("Database pool not available. Cannot initialize database.")
        return

    async with pool.acquire() as connection:
        async with connection.transaction():
            # Accounts Table
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT,
                api_id BYTEA NOT NULL,
                api_hash BYTEA NOT NULL,
                account_name VARCHAR(255) UNIQUE,
                proxy_type TEXT,
                proxy_ip TEXT,
                proxy_port INTEGER,
                proxy_username BYTEA,
                proxy_password BYTEA,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)
            logger.info("Checked/Created 'accounts' table with proxy support.")

            # Sessions Table
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id SERIAL PRIMARY KEY,
                account_id INTEGER NOT NULL UNIQUE REFERENCES accounts(account_id) ON DELETE CASCADE,
                dc_id INTEGER NOT NULL,
                server_address TEXT,
                port INTEGER,
                auth_key_data BYTEA, -- Store raw bytes of the auth key
                pts INTEGER,
                qts INTEGER,
                date BIGINT, -- Store as integer timestamp
                seq INTEGER,
                takeout_id BIGINT,
                last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)
            logger.info("Checked/Created 'sessions' table with new schema.")

            # Modules Table
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_id SERIAL PRIMARY KEY,
                module_name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                version VARCHAR(50),
                module_path VARCHAR(512) NOT NULL, -- Path to the module code
                added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)
            logger.info("Checked/Created 'modules' table.")

            # Account_Modules Table (Junction Table)
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS account_modules (
                account_module_id SERIAL PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
                module_id INTEGER NOT NULL REFERENCES modules(module_id) ON DELETE CASCADE,
                is_active BOOLEAN DEFAULT TRUE,
                configuration TEXT, -- Could be JSON stored as TEXT for module-specific settings
                activated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (account_id, module_id)
            );
            """)
            logger.info("Checked/Created 'account_modules' table.")

            # Logs Table
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                log_id SERIAL PRIMARY KEY,
                account_id INTEGER REFERENCES accounts(account_id) ON DELETE SET NULL, -- Keep logs even if account is deleted
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                level VARCHAR(50) NOT NULL, -- e.g., INFO, ERROR, WARNING
                message TEXT NOT NULL,
                module_name VARCHAR(255) -- Optional: name of the module that generated the log
            );
            """)
            logger.info("Checked/Created 'logs' table.")

            # Module Data Table
            await connection.execute("""
            CREATE TABLE IF NOT EXISTS module_data (
                module_data_id SERIAL PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
                module_name VARCHAR(255) NOT NULL,
                data_key VARCHAR(255) NOT NULL,
                data_value BYTEA NOT NULL, -- Encrypted JSON string
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (account_id, module_name, data_key)
            );
            """)
            logger.info("Checked/Created 'module_data' table.")
            logger.info("Database initialization complete.")

# --- CRUD Operations for Accounts ---
async def add_account(
    api_id: str, 
    api_hash: str, 
    account_name: str, 
    user_telegram_id: Optional[int] = None,
    proxy_type: Optional[str] = None,
    proxy_ip: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None
):
    pool = await get_db_pool()
    if not pool: return None
    try:
        # Encrypt api_id and api_hash before storing
        encrypted_api_id = encryption_manager.encrypt(str(api_id).encode('utf-8'))
        encrypted_api_hash = encryption_manager.encrypt(str(api_hash).encode('utf-8'))
        
        encrypted_proxy_username = None
        if proxy_username:
            encrypted_proxy_username = encryption_manager.encrypt(proxy_username.encode('utf-8'))
        
        encrypted_proxy_password = None
        if proxy_password:
            encrypted_proxy_password = encryption_manager.encrypt(proxy_password.encode('utf-8'))

        async with pool.acquire() as conn:
            query = """
            INSERT INTO accounts (
                api_id, api_hash, account_name, user_telegram_id, 
                proxy_type, proxy_ip, proxy_port, proxy_username, proxy_password, 
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP)
            RETURNING account_id;
            """
            # Use encrypted values in the query
            result = await conn.fetchval(
                query, 
                encrypted_api_id, encrypted_api_hash, account_name, user_telegram_id,
                proxy_type, proxy_ip, proxy_port, encrypted_proxy_username, encrypted_proxy_password
            )
            logger.info(f"Added account '{account_name}' (credentials/proxy encrypted) with ID: {result}")
            return result # Returns the account_id
    except asyncpg.UniqueViolationError:
        logger.warning(f"Account with name '{account_name}' already exists.")
        return None
    except Exception as e:
        logger.error(f"Error adding account '{account_name}': {e}")
        return None

async def get_account(account_id: int = None, account_name: str = None):
    pool = await get_db_pool()
    if not pool: return None
    if not account_id and not account_name:
        logger.warning("get_account called without account_id or account_name")
        return None
    try:
        async with pool.acquire() as conn:
            if account_id:
                query = "SELECT * FROM accounts WHERE account_id = $1;"
                record = await conn.fetchrow(query, account_id)
            else: # account_name must be provided
                query = "SELECT * FROM accounts WHERE account_name = $1;"
                record = await conn.fetchrow(query, account_name)
            
            if record:
                account_data = dict(record)
                try:
                    account_data['api_id'] = encryption_manager.decrypt(record['api_id']).decode('utf-8')
                    account_data['api_hash'] = encryption_manager.decrypt(record['api_hash']).decode('utf-8')

                    if record['proxy_username']:
                        account_data['proxy_username'] = encryption_manager.decrypt(record['proxy_username']).decode('utf-8')
                    if record['proxy_password']:
                        account_data['proxy_password'] = encryption_manager.decrypt(record['proxy_password']).decode('utf-8')
                    
                    return account_data
                except Exception as e:
                    logger.error(f"Failed to decrypt credentials/proxy for account {record['account_id']}: {e}")
                    return None # Or raise, depending on policy
            return None # No record found
    except Exception as e:
        logger.error(f"Error fetching account (id={account_id}, name={account_name}): {e}")
        return None

async def update_account_proxy_settings(
    account_id: int, 
    proxy_type: Optional[str], 
    proxy_ip: Optional[str], 
    proxy_port: Optional[int], 
    encrypted_username: Optional[bytes], 
    encrypted_password: Optional[bytes]
) -> bool:
    pool = await get_db_pool()
    if not pool: 
        logger.error("DB pool not available for update_account_proxy_settings")
        return False
    
    query = """
    UPDATE accounts 
    SET 
        proxy_type = $2, 
        proxy_ip = $3, 
        proxy_port = $4, 
        proxy_username = $5, 
        proxy_password = $6, 
        updated_at = CURRENT_TIMESTAMP 
    WHERE account_id = $1;
    """
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                query, 
                account_id, 
                proxy_type, 
                proxy_ip, 
                proxy_port, 
                encrypted_username, 
                encrypted_password
            )
            updated_count = int(result.split(" ")[1])
            if updated_count > 0:
                logger.info(f"Successfully updated proxy settings for account ID: {account_id}")
                return True
            logger.warning(f"No account found with ID: {account_id} to update proxy settings, or data was the same.")
            return False # No rows affected
    except Exception as e:
        logger.error(f"Error updating proxy settings for account ID {account_id}: {e}")
        return False

async def update_account(account_id: int, **kwargs):
    pool = await get_db_pool()
    if not pool: return False
    if not kwargs:
        logger.warning("update_account called with no fields to update.")
        return False
    
    set_parts = []
    values = []
    valid_fields = ["user_telegram_id", "api_id", "api_hash", "account_name"]
    
    idx = 1
    for key, value in kwargs.items():
        if key in valid_fields:
            set_parts.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
    
    if not set_parts:
        logger.warning("update_account: No valid fields to update provided.")
        return False

    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE accounts SET {', '.join(set_parts)} WHERE account_id = ${idx};"
    values.append(account_id)

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(query, *values)
            updated_count = int(result.split(" ")[1])
            if updated_count > 0:
                logger.info(f"Successfully updated account ID: {account_id}")
                return True
            logger.warning(f"No account found with ID: {account_id} to update or data was the same.")
            return False # Could be True if no change is not an error
    except Exception as e:
        logger.error(f"Error updating account ID {account_id}: {e}")
        return False

async def delete_account(account_id: int):
    pool = await get_db_pool()
    if not pool: return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM accounts WHERE account_id = $1;", account_id)
            deleted_count = int(result.split(" ")[1])
            if deleted_count > 0:
                logger.info(f"Successfully deleted account ID: {account_id} and related data (sessions, account_modules).")
                return True
            logger.warning(f"No account found with ID: {account_id} to delete.")
            return False
    except Exception as e:
        logger.error(f"Error deleting account ID {account_id}: {e}")
        return False

# --- CRUD Operations for Sessions ---
from typing import Optional

async def add_session(
    account_id: int, 
    dc_id: int, 
    server_address: Optional[str], 
    port: Optional[int], 
    auth_key_data: Optional[bytes], 
    pts: Optional[int] = None, 
    qts: Optional[int] = None, 
    date: Optional[int] = None, 
    seq: Optional[int] = None, 
    takeout_id: Optional[int] = None
):
    pool = await get_db_pool()
    if not pool: return None # Or raise an error
    try:
        # Encrypt auth_key_data if it's not None
        db_auth_key_data = auth_key_data 
        if auth_key_data is not None:
            db_auth_key_data = encryption_manager.encrypt(auth_key_data)

        async with pool.acquire() as conn:
            query = """
            INSERT INTO sessions (
                account_id, dc_id, server_address, port, auth_key_data, 
                pts, qts, date, seq, takeout_id, last_used_at, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (account_id) DO UPDATE SET
                dc_id = EXCLUDED.dc_id,
                server_address = EXCLUDED.server_address,
                port = EXCLUDED.port,
                auth_key_data = EXCLUDED.auth_key_data, -- Use db_auth_key_data here
                pts = EXCLUDED.pts,
                qts = EXCLUDED.qts,
                date = EXCLUDED.date,
                seq = EXCLUDED.seq,
                takeout_id = EXCLUDED.takeout_id,
                last_used_at = CURRENT_TIMESTAMP
            RETURNING session_id;
            """
            result = await conn.fetchval(
                query, 
                account_id, dc_id, server_address, port, db_auth_key_data, # Pass encrypted key
                pts, qts, date, seq, takeout_id
            )
            logger.info(f"Added/Updated session (auth_key encrypted) for account ID: {account_id}. Session ID: {result}")
            return result # Returns session_id
    except Exception as e:
        logger.error(f"Error adding/updating session for account ID {account_id}: {e}", exc_info=True)
        return None

async def get_session(account_id: int):
    pool = await get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            # Fetch all the new fields
            record = await conn.fetchrow(
                "SELECT session_id, account_id, dc_id, server_address, port, auth_key_data, "
                "pts, qts, date, seq, takeout_id, last_used_at, created_at "
                "FROM sessions WHERE account_id = $1;", 
                account_id
            )
            if record and record['auth_key_data'] is not None:
                try:
                    decrypted_auth_key_data = encryption_manager.decrypt(record['auth_key_data'])
                    # Return a new dictionary with decrypted auth_key_data
                    return dict(record, auth_key_data=decrypted_auth_key_data)
                except Exception as e:
                    logger.error(f"Failed to decrypt session auth_key for account {record['account_id']}: {e}")
                    # Session is unusable if auth key can't be decrypted.
                    # Depending on policy, could return a record that DbSession can identify as problematic,
                    # or None to force re-login. For now, None seems safer.
                    return None 
            return record # Return original record if no auth_key_data or if decryption not needed
    except Exception as e:
        logger.error(f"Error fetching session for account ID {account_id}: {e}", exc_info=True)
        return None

# update_session is effectively replaced by add_session's ON CONFLICT clause
# async def update_session(...):
#    pass 

async def delete_session(account_id: int):
    pool = await get_db_pool()
    if not pool: return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM sessions WHERE account_id = $1;", account_id)
            deleted_count = int(result.split(" ")[1])
            if deleted_count > 0:
                logger.info(f"Successfully deleted session for account ID: {account_id}")
                return True
            logger.warning(f"No session found for account ID: {account_id} to delete.")
            return False
    except Exception as e:
        logger.error(f"Error deleting session for account ID {account_id}: {e}")
        return False

# --- CRUD Operations for Modules ---
async def add_module(module_name: str, module_path: str, description: str = None, version: str = None):
    pool = await get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            query = """
            INSERT INTO modules (module_name, module_path, description, version)
            VALUES ($1, $2, $3, $4)
            RETURNING module_id;
            """
            result = await conn.fetchval(query, module_name, module_path, description, version)
            logger.info(f"Added module '{module_name}' with ID: {result}")
            return result
    except asyncpg.UniqueViolationError:
        logger.warning(f"Module with name '{module_name}' already exists.")
        # Optionally, update existing module or return its ID
        existing_module = await get_module(module_name=module_name)
        return existing_module['module_id'] if existing_module else None
    except Exception as e:
        logger.error(f"Error adding module '{module_name}': {e}")
        return None

async def get_module(module_id: int = None, module_name: str = None):
    pool = await get_db_pool()
    if not pool: return None
    if not module_id and not module_name:
        logger.warning("get_module called without module_id or module_name")
        return None
    try:
        async with pool.acquire() as conn:
            if module_id:
                record = await conn.fetchrow("SELECT * FROM modules WHERE module_id = $1;", module_id)
            else:
                record = await conn.fetchrow("SELECT * FROM modules WHERE module_name = $1;", module_name)
            return record
    except Exception as e:
        logger.error(f"Error fetching module (id={module_id}, name={module_name}): {e}")
        return None

async def get_all_modules():
    pool = await get_db_pool()
    if not pool: return []
    try:
        async with pool.acquire() as conn:
            records = await conn.fetch("SELECT * FROM modules ORDER BY module_name;")
            return records
    except Exception as e:
        logger.error(f"Error fetching all modules: {e}")
        return []

async def delete_module(module_id: int):
    pool = await get_db_pool()
    if not pool: return False
    try:
        async with pool.acquire() as conn:
            # ON DELETE CASCADE in account_modules will handle unlinking
            result = await conn.execute("DELETE FROM modules WHERE module_id = $1;", module_id)
            deleted_count = int(result.split(" ")[1])
            if deleted_count > 0:
                logger.info(f"Successfully deleted module ID: {module_id}")
                return True
            logger.warning(f"No module found with ID: {module_id} to delete.")
            return False
    except Exception as e:
        logger.error(f"Error deleting module ID {module_id}: {e}")
        return False

# --- CRUD Operations for Account_Modules (Linking Table) ---
async def link_module_to_account(account_id: int, module_id: int, configuration: str = None, is_active: bool = True):
    pool = await get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            query = """
            INSERT INTO account_modules (account_id, module_id, configuration, is_active, updated_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (account_id, module_id) DO UPDATE
            SET configuration = EXCLUDED.configuration, is_active = EXCLUDED.is_active, updated_at = CURRENT_TIMESTAMP
            RETURNING account_module_id;
            """
            result = await conn.fetchval(query, account_id, module_id, configuration, is_active)
            logger.info(f"Linked/Updated module ID {module_id} to account ID {account_id}. Link ID: {result}")
            return result
    except Exception as e:
        logger.error(f"Error linking module {module_id} to account {account_id}: {e}")
        return None

async def get_account_module(account_id: int, module_id: int):
    pool = await get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM account_modules WHERE account_id = $1 AND module_id = $2;",
                account_id, module_id
            )
            return record
    except Exception as e:
        logger.error(f"Error fetching account_module link for account {account_id}, module {module_id}: {e}")
        return None

async def get_active_modules_for_account(account_id: int):
    pool = await get_db_pool()
    if not pool: return []
    try:
        async with pool.acquire() as conn:
            query = """
            SELECT m.*, am.configuration, am.account_module_id
            FROM modules m
            JOIN account_modules am ON m.module_id = am.module_id
            WHERE am.account_id = $1 AND am.is_active = TRUE;
            """
            records = await conn.fetch(query, account_id)
            return records
    except Exception as e:
        logger.error(f"Error fetching active modules for account ID {account_id}: {e}")
        return []

async def update_account_module(account_module_id: int, configuration: str = None, is_active: bool = None):
    pool = await get_db_pool()
    if not pool: return False
    if configuration is None and is_active is None:
        logger.warning("update_account_module called with no fields to update.")
        return False

    set_parts = []
    values = []
    idx = 1

    if configuration is not None:
        set_parts.append(f"configuration = ${idx}")
        values.append(configuration)
        idx += 1
    if is_active is not None:
        set_parts.append(f"is_active = ${idx}")
        values.append(is_active)
        idx += 1
    
    if not set_parts: # Should not happen due to initial check, but good practice
        return False

    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE account_modules SET {', '.join(set_parts)} WHERE account_module_id = ${idx};"
    values.append(account_module_id)

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(query, *values)
            updated_count = int(result.split(" ")[1])
            if updated_count > 0:
                logger.info(f"Successfully updated account_module ID: {account_module_id}")
                return True
            logger.warning(f"No account_module found with ID: {account_module_id} to update or data was the same.")
            return False
    except Exception as e:
        logger.error(f"Error updating account_module ID {account_module_id}: {e}")
        return False

async def unlink_module_from_account(account_id: int, module_id: int): # Or by account_module_id
    pool = await get_db_pool()
    if not pool: return False
    try:
        async with pool.acquire() as conn:
            # Alternative: by account_module_id if preferred
            # query = "DELETE FROM account_modules WHERE account_module_id = $1;"
            query = "DELETE FROM account_modules WHERE account_id = $1 AND module_id = $2;"
            result = await conn.execute(query, account_id, module_id)
            deleted_count = int(result.split(" ")[1])
            if deleted_count > 0:
                logger.info(f"Successfully unlinked module {module_id} from account {account_id}")
                return True
            logger.warning(f"No link found for module {module_id} and account {account_id} to delete.")
            return False
    except Exception as e:
        logger.error(f"Error unlinking module {module_id} from account {account_id}: {e}")
        return False

# --- CRUD Operations for Logs ---
async def add_log(level: str, message: str, account_id: int = None, module_name: str = None):
    pool = await get_db_pool()
    if not pool: return None # Or some other indicator of failure
    try:
        async with pool.acquire() as conn:
            query = """
            INSERT INTO logs (account_id, level, message, module_name)
            VALUES ($1, $2, $3, $4)
            RETURNING log_id;
            """
            log_id = await conn.fetchval(query, account_id, level, message, module_name)
            # Avoid logging INFO logs to prevent recursive logging if logger itself uses this
            if level.upper() not in ["INFO", "DEBUG"]: 
                logger.log(logging.getLevelName(level.upper()), f"DB Logged: {message[:100]}... (ID: {log_id})")
            return log_id
    except Exception as e:
        # Be careful with logging errors here if this function is used by the logger itself
        print(f"CRITICAL: Error adding log to database: {e}") # Direct print to avoid loop
        return None

async def get_logs(account_id: int = None, limit: int = 100, level: str = None):
    pool = await get_db_pool()
    if not pool: return []
    try:
        async with pool.acquire() as conn:
            conditions = []
            values = []
            idx = 1

            if account_id is not None:
                conditions.append(f"account_id = ${idx}")
                values.append(account_id)
                idx += 1
            if level is not None:
                conditions.append(f"level = ${idx}")
                values.append(level.upper())
                idx += 1
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"SELECT * FROM logs {where_clause} ORDER BY timestamp DESC LIMIT ${idx};"
            values.append(limit)
            
            records = await conn.fetch(query, *values)
            return records
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return []

# --- CRUD Operations for Module Data ---
async def save_module_data(account_id: int, module_name: str, key: str, value: Any) -> bool:
    pool = await get_db_pool()
    if not pool: return False
    try:
        json_value = json.dumps(value)
        encrypted_value = encryption_manager.encrypt(json_value.encode('utf-8'))
        async with pool.acquire() as conn:
            query = """
            INSERT INTO module_data (account_id, module_name, data_key, data_value, updated_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (account_id, module_name, data_key) DO UPDATE
            SET data_value = EXCLUDED.data_value, updated_at = CURRENT_TIMESTAMP;
            """
            await conn.execute(query, account_id, module_name, key, encrypted_value)
            logger.info(f"Saved data for module '{module_name}', key '{key}', account '{account_id}'.")
            return True
    except Exception as e:
        logger.error(f"Error saving data for module '{module_name}', key '{key}', account '{account_id}': {e}", exc_info=True)
        return False

async def get_module_data(account_id: int, module_name: str, key: str) -> Any:
    pool = await get_db_pool()
    if not pool: return None
    try:
        async with pool.acquire() as conn:
            query = "SELECT data_value FROM module_data WHERE account_id = $1 AND module_name = $2 AND data_key = $3;"
            record = await conn.fetchrow(query, account_id, module_name, key)
            if record and record['data_value']:
                decrypted_value = encryption_manager.decrypt(record['data_value'])
                value = json.loads(decrypted_value.decode('utf-8'))
                logger.info(f"Retrieved data for module '{module_name}', key '{key}', account '{account_id}'.")
                return value
            logger.info(f"No data found for module '{module_name}', key '{key}', account '{account_id}'.")
            return None
    except Exception as e:
        logger.error(f"Error retrieving data for module '{module_name}', key '{key}', account '{account_id}': {e}", exc_info=True)
        return None

async def delete_module_data(account_id: int, module_name: str, key: str) -> bool:
    pool = await get_db_pool()
    if not pool: return False
    try:
        async with pool.acquire() as conn:
            query = "DELETE FROM module_data WHERE account_id = $1 AND module_name = $2 AND data_key = $3;"
            result = await conn.execute(query, account_id, module_name, key)
            deleted_count = int(result.split(" ")[1])
            if deleted_count > 0:
                logger.info(f"Deleted data for module '{module_name}', key '{key}', account '{account_id}'.")
                return True
            logger.warning(f"No data found to delete for module '{module_name}', key '{key}', account '{account_id}'.")
            return False
    except Exception as e:
        logger.error(f"Error deleting data for module '{module_name}', key '{key}', account '{account_id}': {e}", exc_info=True)
        return False

async def get_all_module_data(account_id: int, module_name: str) -> dict:
    pool = await get_db_pool()
    if not pool: return {}
    results = {}
    try:
        async with pool.acquire() as conn:
            query = "SELECT data_key, data_value FROM module_data WHERE account_id = $1 AND module_name = $2;"
            records = await conn.fetch(query, account_id, module_name)
            for record in records:
                try:
                    decrypted_value = encryption_manager.decrypt(record['data_value'])
                    value = json.loads(decrypted_value.decode('utf-8'))
                    results[record['data_key']] = value
                except Exception as e_decrypt:
                    logger.error(f"Error decrypting/deserializing data for module '{module_name}', key '{record['data_key']}', account '{account_id}': {e_decrypt}")
            logger.info(f"Retrieved all data for module '{module_name}', account '{account_id}'. Found {len(results)} items.")
            return results
    except Exception as e:
        logger.error(f"Error retrieving all data for module '{module_name}', account '{account_id}': {e}", exc_info=True)
        return {}


if __name__ == '__main__':
    # This is an example of how to initialize and use the db_manager.
    # You'd typically call these from other parts of your application.
    import asyncio

    async def main_test_logic():
        try:
            # IMPORTANT: Ensure your PostgreSQL server is running and accessible
            # with credentials/db name defined by environment variables or the defaults.
            # E.g., run the docker-compose generated in the previous subtask.
            
            await initialize_database()
            logger.info("Database initialized (or tables already existed).")

            # --- Test Accounts ---
            # Note: API_ID and API_HASH are now stored encrypted.
            # The test logic for add_account and get_account will need to be aware that
            # get_account returns a dict with decrypted values, not a raw record.
            # The session_string_example_12345 in add_session test is no longer valid.
            # Session tests will need to be updated to reflect new add_session/get_session parameters.
            acc_name = "test_user_main_encrypted"
            # Ensure test API ID/Hash are strings, as add_account expects strings to encode.
            test_api_id_plain = "1234500" 
            test_api_hash_plain = "apihashxyz00"

            acc_id = await add_account(
                api_id=test_api_id_plain, 
                api_hash=test_api_hash_plain, 
                account_name=acc_name, 
                user_telegram_id=777001
            )
            if acc_id:
                logger.info(f"Account '{acc_name}' added with ID: {acc_id}")
                ret_acc = await get_account(account_name=acc_name) # This will be a dict
                if ret_acc:
                    logger.info(f"Retrieved account (decrypted): {ret_acc}")
                    assert ret_acc['api_id'] == test_api_id_plain
                    assert ret_acc['api_hash'] == test_api_hash_plain
                else:
                    logger.error(f"Could not retrieve account '{acc_name}' after adding.")
                
                # Test update (update_account not modified for encryption in this step, be cautious if updating api_id/hash)
                await update_account(acc_id, account_name=f"{acc_name}_updated")
                ret_acc_updated = await get_account(account_id=acc_id)
                logger.info(f"Updated account name: {ret_acc_updated['account_name'] if ret_acc_updated else 'Not found'}")
            else:
                # If already exists from previous run, try to get it
                logger.info(f"Account '{acc_name}' might already exist. Trying to fetch...")
                ret_acc = await get_account(account_name=acc_name)
                if ret_acc:
                    acc_id = ret_acc['account_id']
                    logger.info(f"Account '{acc_name}' already existed with ID: {acc_id}. API ID (decrypted): {ret_acc['api_id']}")
                    assert ret_acc['api_id'] == test_api_id_plain # Verify decryption
                else:
                    logger.error(f"Failed to add or find account '{acc_name}'")
                    # return # Stop test if base account fails

            # --- Test Sessions (Updated for new add_session/get_session structure) ---
            if acc_id:
                # Example session data (auth_key_data should be bytes)
                test_auth_key_data = os.urandom(256) # Simulate a real auth key (bytes)
                
                session_id = await add_session(
                    account_id=acc_id,
                    dc_id=2,
                    server_address="149.154.167.51",
                    port=443,
                    auth_key_data=test_auth_key_data, # This will be encrypted
                    pts=100, qts=200, date=int(os.times()[0]), seq=300 
                )
                if session_id:
                    logger.info(f"Session added/updated for account {acc_id}, session ID: {session_id}")
                    ret_sess = await get_session(acc_id) # This will be a dict with decrypted auth_key
                    if ret_sess and ret_sess['auth_key_data']:
                        logger.info(f"Retrieved session. Auth key data length: {len(ret_sess['auth_key_data'])}")
                        assert ret_sess['auth_key_data'] == test_auth_key_data, "Decrypted auth_key_data mismatch"
                    elif ret_sess:
                         logger.info(f"Retrieved session but auth_key_data is None: {ret_sess}")
                    else:
                        logger.error(f"Could not retrieve session for account {acc_id} after adding.")
                else:
                    logger.error(f"Failed to add session for account {acc_id}.")
            
            # --- Test Modules ---
            mod_name = "test_module_alpha"
            mod_id = await add_module(module_name=mod_name, module_path="/path/to/module_alpha.py", description="A test module")
            if mod_id:
                logger.info(f"Module '{mod_name}' added with ID: {mod_id}")
                ret_mod = await get_module(module_name=mod_name)
                logger.info(f"Retrieved module: {dict(ret_mod) if ret_mod else 'Not found'}")
            else:
                ret_mod = await get_module(module_name=mod_name)
                if ret_mod:
                    mod_id = ret_mod['module_id']
                    logger.info(f"Module '{mod_name}' already existed with ID: {mod_id}")
                else:
                    logger.error(f"Failed to add or find module '{mod_name}'")


            # --- Test Account_Modules (Linking) ---
            if acc_id and mod_id:
                link_id = await link_module_to_account(acc_id, mod_id, configuration='{"setting": "value"}')
                if link_id:
                    logger.info(f"Linked module {mod_id} to account {acc_id}. Link ID: {link_id}")
                    active_mods = await get_active_modules_for_account(acc_id)
                    logger.info(f"Active modules for account {acc_id}: {len(active_mods)} found.")
                    for m in active_mods: logger.info(f"  - {m['module_name']}, config: {m['configuration']}")
                    
                    if active_mods: # Assuming the first one is the one we just added
                        account_module_link_id = active_mods[0]['account_module_id']
                        await update_account_module(account_module_link_id, is_active=False)
                        logger.info(f"Deactivated module link ID {account_module_link_id}")
                        active_mods_after_update = await get_active_modules_for_account(acc_id)
                        logger.info(f"Active modules for account {acc_id} after deactivation: {len(active_mods_after_update)} found.")


            # --- Test Logs ---
            log_id = await add_log("INFO", "Test log message from main_test_logic", account_id=acc_id, module_name=mod_name)
            if log_id:
                logger.info(f"Added log with ID: {log_id}")
            
            error_log_id = await add_log("ERROR", "This is a test error log.", account_id=acc_id)
            if error_log_id:
                logger.info(f"Added error log with ID: {error_log_id}")

            all_logs = await get_logs(account_id=acc_id, limit=5)
            logger.info(f"Retrieved last 5 logs for account {acc_id}:")
            for log_entry in all_logs:
                logger.info(f"  - [{log_entry['timestamp']}] [{log_entry['level']}] {log_entry['message']}")
            
            # --- Test Deletions (optional, be careful with order) ---
            # ... (existing deletion tests can remain here)

            # --- Test Module Data ---
            if acc_id: # Ensure we have an account ID
                test_module_name = "test_module_for_data"
                
                # 1. Save some data
                data1 = {"setting1": "value1", "count": 10}
                data2 = [1, 2, "string_value", {"nested_key": "nested_val"}]
                
                await save_module_data(acc_id, test_module_name, "config_main", data1)
                await save_module_data(acc_id, test_module_name, "user_list", data2)
                logger.info(f"Saved initial data for module '{test_module_name}'.")

                # 2. Retrieve one piece of data
                ret_data1 = await get_module_data(acc_id, test_module_name, "config_main")
                if ret_data1:
                    logger.info(f"Retrieved 'config_main' for '{test_module_name}': {ret_data1}")
                    assert ret_data1 == data1, "Retrieved data does not match original for 'config_main'"
                else:
                    logger.error(f"Could not retrieve 'config_main' for '{test_module_name}'.")

                # 3. Retrieve all data for the module
                all_mod_data = await get_all_module_data(acc_id, test_module_name)
                logger.info(f"Retrieved all data for '{test_module_name}': {all_mod_data}")
                assert len(all_mod_data) == 2, f"Expected 2 items, got {len(all_mod_data)}"
                assert all_mod_data.get("config_main") == data1, "All data retrieval mismatch for 'config_main'"
                assert all_mod_data.get("user_list") == data2, "All data retrieval mismatch for 'user_list'"

                # 4. Update existing data
                updated_data1 = {"setting1": "value_updated", "count": 11, "new_field": True}
                await save_module_data(acc_id, test_module_name, "config_main", updated_data1)
                ret_updated_data1 = await get_module_data(acc_id, test_module_name, "config_main")
                logger.info(f"Retrieved updated 'config_main': {ret_updated_data1}")
                assert ret_updated_data1 == updated_data1, "Updated data does not match"

                # 5. Delete one piece of data
                delete_result = await delete_module_data(acc_id, test_module_name, "user_list")
                logger.info(f"Deletion of 'user_list' for '{test_module_name}': {'Success' if delete_result else 'Failed'}")
                assert delete_result, "Delete operation failed for 'user_list'"
                
                ret_after_delete = await get_module_data(acc_id, test_module_name, "user_list")
                assert ret_after_delete is None, "Data 'user_list' still exists after deletion."

                all_mod_data_after_delete = await get_all_module_data(acc_id, test_module_name)
                logger.info(f"All data for '{test_module_name}' after deleting one key: {all_mod_data_after_delete}")
                assert len(all_mod_data_after_delete) == 1, "Expected 1 item after deletion"
                assert "user_list" not in all_mod_data_after_delete, "'user_list' key still present in all_mod_data"
                assert all_mod_data_after_delete.get("config_main") == updated_data1

                # 6. Delete remaining data
                await delete_module_data(acc_id, test_module_name, "config_main")
                all_mod_data_final = await get_all_module_data(acc_id, test_module_name)
                assert not all_mod_data_final, "Module data not empty after final delete"
                logger.info(f"All data for module '{test_module_name}' successfully deleted.")

            else:
                logger.warning("Skipping module_data tests as acc_id is not available.")


        except Exception as e:
            logger.error(f"An error occurred in main_test_logic: {e}", exc_info=True)
        finally:
            await close_db_pool() # Close the pool when done
            logger.info("Main test logic finished. DB Pool closed.")

    # To run this test part:
    # 1. Ensure PostgreSQL is running and configured (e.g., via docker-compose from previous step).
    #   The initialize_database() will attempt to update the schema if run.
    #   Ensure USERBOT_ENCRYPTION_KEY is set in your environment for these tests.
    # 2. Set environment variables DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME if not using defaults.
    # 3. Uncomment the line below:
    # asyncio.run(main_test_logic())
    logger.info("userbot/src/db_manager.py updated for per-account proxy settings and encryption of API creds/session auth_key/proxy creds.")
