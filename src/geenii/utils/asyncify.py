import asyncio
from functools import wraps

def asyncify(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return wrapper