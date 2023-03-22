import asyncio
import random  # just for testing
from client.client_logger import ClientLogger

# Order of operations
# Start the client listener and connect to the game
# When the client connects
test_game_messages = ["asdf\n", "yada\n", "waza\n", "yerp\n"]
# The client will store messages in the client buffer until the write_to_game task picks them up
client_buffer = asyncio.Queue(maxsize=100)
# The game buffer will hold messages from the game socket until the write_to_client task picks them up
game_buffer = asyncio.Queue(maxsize=1_000)

log = ClientLogger().log


async def connect_to_game():
    log.info("Connecting to game")
    await client_buffer.put("Connecting to game")
    asyncio.create_task(read_from_game(None))


async def write_to_client(writer):
    log.info("Starting client writer loop")
    while True:
        if not game_buffer.empty():
            # Queue.get blocks until it gets an item
            message = await game_buffer.get()
            log.info(f"Sending to client: {message}")
            writer.write(message)
            asyncio.create_task(writer.drain())


async def read_from_client(reader):
    log.info("Starting client reader loop")
    while True:
        recv = await reader.readline()
        log.info(f"Received: {recv}")
        if not recv:
            return
        await client_buffer.put(recv.encode())


async def handle_client(reader, writer):
    log.info(f"Got connection from {writer.get_extra_info('peername')}")
    write_task = asyncio.create_task(write_to_client(writer))
    read_task = asyncio.create_task(read_from_client(reader))
    # Producer and consumer need to start in parallel: https://stackoverflow.com/questions/56377402/why-is-asyncio-queue-await-get-blocking
    await asyncio.gather(write_task, read_task)


async def read_from_game(reader):
    # Placeholder test that adds a message to the game buffer every 10 seconds
    while True:
        message = random.choice(test_game_messages).encode("ASCII")
        await game_buffer.put(message)
        await asyncio.sleep(10)


async def write_to_game(writer):
    pass


async def handle_game(reader, writer):
    pass


async def listen_for_client():
    log.info("Listening for front-end/client")
    client_server = await asyncio.start_server(handle_client, "127.0.0.1", 10002)
    async with client_server:
        await client_server.serve_forever()


async def handle_game_buffer():
    pass


async def handle_client_buffer():
    pass


async def main():
    try:
        client_task = asyncio.create_task(listen_for_client())
        game_task = asyncio.create_task(connect_to_game())
        await asyncio.gather(client_task, game_task)
    except Exception:
        client_task.cancel()
        game_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
