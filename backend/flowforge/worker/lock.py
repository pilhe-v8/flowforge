from uuid import uuid4


class SessionLock:
    """Distributed Redis lock for a session, preventing concurrent processing."""

    def __init__(self, redis_client, session_id: str, ttl: int = 120):
        self.redis = redis_client
        self.key = f"flowforge:lock:{session_id}"
        self.ttl = ttl
        self.token = uuid4().hex
        self.acquired = False

    async def __aenter__(self):
        result = await self.redis.set(self.key, self.token, nx=True, ex=self.ttl)
        self.acquired = bool(result)
        return self

    async def __aexit__(self, *args):
        if self.acquired:
            lua = (
                'if redis.call("get", KEYS[1]) == ARGV[1] then '
                '  return redis.call("del", KEYS[1]) '
                "else "
                "  return 0 "
                "end"
            )
            await self.redis.eval(lua, 1, self.key, self.token)
