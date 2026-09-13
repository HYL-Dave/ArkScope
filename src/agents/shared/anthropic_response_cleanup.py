"""Own async child response finalizers, including SDK pre-stream error paths."""

import asyncio

import httpx2


class _JoinedCloseStream(httpx2.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream
        self.closing = None

    async def __aiter__(self):
        async for chunk in self.stream:
            yield chunk

    async def aclose(self):
        if self.closing is None:
            self.closing = asyncio.create_task(self.stream.aclose())
        try:
            await asyncio.shield(self.closing)
        except asyncio.CancelledError:
            while not self.closing.done():
                try:
                    await asyncio.shield(self.closing)
                except asyncio.CancelledError:
                    continue
                except BaseException:
                    break
            if not self.closing.cancelled():
                self.closing.exception()
            raise


class AnthropicResponseCleanup:
    """Public SDK middleware observes every HTTP attempt before retry/error handling."""

    def __init__(self):
        self.responses = []

    async def observe(self, request, call_next):
        result = await call_next(request)
        response = result.http_response
        response.stream = _JoinedCloseStream(response.stream)
        self.responses.append(response)
        return result

    async def close(self):
        # Terminal error-body cancellation need not enter the SDK stream manager.
        # Close all observed responses before the invocation's client is released.
        responses, self.responses = self.responses, []
        results = await asyncio.gather(*(response.aclose() for response in responses),
                                       return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result
