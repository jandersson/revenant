import asyncio
import random  # just for testing
from client.client_logger import ClientLogger

# The client will store messages in the client buffer until the write_to_game task picks them up
client_buffer = asyncio.Queue(maxsize=100)
# The game buffer will hold messages from the game socket until the write_to_client task picks them up
game_buffer = asyncio.Queue(maxsize=1_000)

log = ClientLogger().log


def connect_to_game():
    pass


async def write_to_client(writer):
    # Just mocking a connection to try this out
    random_messages = ["asdf\n", "yada\n"]
    while True:
        message = random.choice(random_messages).encode("ASCII")
        writer.write(message)
        log.info(f"Sending to client: {message}")
        asyncio.create_task(writer.drain())
        await asyncio.sleep(10)


async def read_from_client(reader):
    while True:
        recv = await reader.readline()
        log.info(f"Received: {recv}")
        if not recv:
            return
        asyncio.create_task(client_buffer.put(recv.encode()))


async def handle_client(reader, writer):
    log.info(f"Got connection from {writer.get_extra_info('peername')}")
    asyncio.create_task(write_to_client(writer))
    asyncio.create_task(read_from_client(reader))


async def read_from_game(reader):
    pass


async def write_to_game(writer):
    pass


async def handle_game(reader, writer):
    pass


async def listen_for_client():
    client_server = await asyncio.start_server(handle_client, "127.0.0.1", 10002)
    async with client_server:
        await client_server.serve_forever()


def handle_game_buffer():
    pass


def handle_client_buffer():
    pass


asyncio.run(listen_for_client())
