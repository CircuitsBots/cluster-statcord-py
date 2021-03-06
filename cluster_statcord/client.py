import asyncio
import aiohttp
import psutil
from discord import Client as DiscordClient
from . import exceptions
import contextlib


class Client:
    """Client for using the statcord API"""

    def __init__(self, bot, token, cluster_id, **kwargs):
        if not isinstance(bot, DiscordClient):
            raise TypeError(
                "Expected class deriving from discord.Client "
                f"for arg bot not {bot.__class__.__qualname__}"
            )
        if not isinstance(token, str):
            raise TypeError(
                "Expected str for arg token not "
                f"{token.__class__.__qualname__}"
            )

        self.bot = bot
        self.key = token
        self.cluster_id = cluster_id
        self.base = "https://api.statcord.com/v3/"
        self.session = aiohttp.ClientSession(loop=bot.loop)

        if kwargs.get("mem"):
            if isinstance(kwargs["mem"], bool):
                self.mem = kwargs["mem"]
            else:
                raise TypeError(
                    "Memory config : expected type bool not "
                    f"{kwargs['mem'].__class__.__qualname__}"
                )
        else:
            self.mem = True

        if kwargs.get("cpu"):
            if isinstance(kwargs["cpu"], bool):
                self.cpu = kwargs["cpu"]
            else:
                raise TypeError(
                    f"CPU config : expected type bool not "
                    f"{kwargs['cpu'].__class__.__qualname__}"
                )
        else:
            self.cpu = True

        if kwargs.get("bandwidth"):
            if isinstance(kwargs["bandwidth"], bool):
                self.bandwidth = kwargs["bandwidth"]
            else:
                raise TypeError("Bandwidth config : expected type bool")
        else:
            self.bandwidth = True

        if kwargs.get("debug"):
            if isinstance(kwargs["debug"], bool):
                self.debug = kwargs["debug"]
            else:
                raise TypeError(
                    "Debug config : expected type bool not "
                    f"{kwargs['debug'].__class__.__qualname__}"
                )
        else:
            self.debug = False

        self.active = []
        self.commands = 0
        self.popular = []
        self.previous_bandwidth = (
            psutil.net_io_counters().bytes_sent
            + psutil.net_io_counters().bytes_recv
        )
        psutil.cpu_percent()

        if self.debug:
            print("Statcord debug mode enabled")

    def __headers(self):
        return {"Content-Type": "application/json"}

    async def __handle_response(self, res: aiohttp.ClientResponse) -> dict:
        try:
            msg = await res.json() or {}
        except aiohttp.ContentTypeError:
            msg = await res.text()
        status = res.status
        if status == 200:
            return msg
        elif status == 429:
            raise exceptions.TooManyRequests(status, msg, int(msg.get("wait")))
        else:
            raise exceptions.RequestFailure(status=status, response=msg)

    @property
    def servers(self):
        return str(len(self.bot.guilds))

    @property
    def _user_counter(self):
        for g in self.bot.guilds:
            with contextlib.suppress(AttributeError):
                yield g.member_count

    @property
    def users(self):
        return str(sum(self._user_counter))

    async def post_data(self):
        id = str(self.bot.user.id)
        commands = str(self.commands)

        if self.mem:
            mem = psutil.virtual_memory()
            memactive = str(mem.used)
            memload = str(mem.percent)
        else:
            memactive = "0"
            memload = "0"

        if self.cpu:
            cpuload = str(psutil.cpu_percent())
        else:
            cpuload = "0"

        if self.bandwidth:
            current_bandwidth = (
                psutil.net_io_counters().bytes_sent
                + psutil.net_io_counters().bytes_recv
            )
            bandwidth = str(current_bandwidth - self.previous_bandwidth)
            self.previous_bandwidth = current_bandwidth
        else:
            bandwidth = "0"

        data = {
            "id": id,
            "key": self.key,
            "servers": self.servers,
            "users": self.users,
            "commands": commands,
            "active": self.active,
            "popular": self.popular,
            "memactive": memactive,
            "memload": memload,
            "cpuload": cpuload,
            "bandwidth": bandwidth,
            "cluster_id": self.cluster_id
        }
        if self.debug:
            print("Posting data")
            print(data)
        self.active = []
        self.commands = 0
        self.popular = []

        async with self.session.post(
            url=self.base + "clusters", json=data, headers=self.__headers()
        ) as resp:
            res = await self.__handle_response(resp)
            if self.debug:
                print(res)

    def start_loop(self):
        self.bot.loop.create_task(self.__loop())

    def command_run(self, ctx):
        self.commands += 1
        if ctx.author.id not in self.active:
            self.active.append(ctx.author.id)

        command = ctx.command.name
        found = False
        popular = list(self.popular)
        self.popular = []
        for cmd in popular:
            if cmd["name"] == command:
                found = True
                cmd["count"] = str(int(cmd["count"]) + 1)
            self.popular.append(cmd)

        if not found:
            self.popular.append({"name": command, "count": "1"})

    async def __loop(self):
        """
        The internal loop used for automatically posting server/guild
        count stats
        """
        await self.bot.wait_until_ready()
        if self.debug:
            print("Statcord Auto Post has started!")
        while not self.bot.is_closed():
            try:
                await self.post_data()
            except Exception as e:
                await self.on_error(e)
            await asyncio.sleep(60)

    async def on_error(self, error):
        print(
            "Statcord posting exception occured: "
            f"{error.__class__.__qualname__} - {error}"
        )
