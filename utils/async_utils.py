# 비동기 함수를 동기적으로 실행하기 위한 유틸

import asyncio

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

def run_async(coro):
    return _loop.run_until_complete(coro)