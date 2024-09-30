import asyncpg
import asyncio
from userbot import logger


class AIOPostgresDB:
    def __init__(
        self,
        database: str,
        user: str,
        password: str,
        host: str = "localhost",
        port: int = 5432,
        create_table: str = "",
    ):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database
        self.create_table = create_table
        asyncio.run(self.init_db())

    async def __aenter__(self):
        self.connection = await self.init_db()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.connection.close()

    async def __call__(self, message):
        record = message.record
        log_level = record["level"].name
        log_message = record["message"]
        async with self.connection.transaction():
            await self.connection.execute(
                """
        INSERT INTO logs(log_level, message) VALUES($1, $2)
    """,
                log_level,
                log_message,
            )

    async def init_db(self):
        self.connection = await asyncpg.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            port=self.port,
            database=self.database,
        )
        if self.create_table:
            async with connection.transaction():
                await connection.execute(self.create_table)
                logger.success("Table created successfully")

    async def write(self, table: str, columns: str, values: str) -> bool:
        logger.debug(f"INSERT INTO {table} ({columns}) VALUES ({values})")
        async with self.connection.transaction():
            await self.connection.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({values})"
            )
            return True

    async def read(self, table: str, columns: str, requirement: str = ""):
        logger.debug(
            f"SELECT {columns} FROM {table}" + f" WHERE {requirement}"
            if requirement
            else ""
        )
        query = f"SELECT {columns} FROM {table}"
        if requirement:
            query += f" WHERE {requirement}"
        return await self.connection.fetch(query)

    async def update(self, table: str, data: str, requirement: str) -> bool:
        logger.debug(f"UPDATE {table} SET {data} WHERE {requirement}")
        query = f"UPDATE {table} SET {data} WHERE {requirement}"
        async with self.connection.transaction():
            await self.connection.execute(query)
            return True

    async def delete(self, table: str, requirement: str) -> bool:
        logger.debug(f"DELETE FROM {table} WHERE {requirement}")
        query = f"DELETE FROM {table} WHERE {requirement}"
        async with self.connection.transaction():
            await self.connection.execute(query)
            return True
