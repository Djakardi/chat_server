import asyncio


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, bufsize: int = 4096
) -> None:
    """Coroutine invoked for each incoming connection.

    It reads raw bytes from `reader`, logs them, and echoes them back to the
    peer. When the client closes the connection the coroutine returns.
    """
    peer = writer.get_extra_info("peername")
    print("Connected by", peer)
    try:
        while True:
            data = await reader.read(bufsize)
            if not data:  # EOF — client closed connection
                print("Connection closed by client")
                break
            print("Received raw bytes:", data)
            writer.write(data)  # echo
            await writer.drain()
    except asyncio.CancelledError:
        # server is shutting down; just close cleanly
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def start_raw_tcp_server(
    host: str = "0.0.0.0", port: int = 9000, bufsize: int = 4096
) -> None:
    """Async TCP server example using :mod:`asyncio`.

    The semantics are identical to the previous synchronous example, but the
    implementation uses ``asyncio.start_server`` so multiple clients can be
    handled concurrently without threads.

    Running from the command line is the same as before:

    ```sh
    $ python -m src.proxy          # listens on port 9000
    Listening on 0.0.0.0:9000
    ```

    Under the hood ``asyncio`` schedules ``handle_client`` for each connection,
    returning control to the event loop whenever it awaits I/O.
    """
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, bufsize), host, port
    )
    addr = server.sockets[0].getsockname()
    print(f"Listening on {addr[0]}:{addr[1]}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    # run the async server when executed directly
    asyncio.run(start_raw_tcp_server())
