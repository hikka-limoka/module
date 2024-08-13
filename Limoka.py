import aiohttp

from hikkatl.types import Message
from .. import utils, loader


# meta developer: @limokanews

@loader.tds
class Limoka(loader.Module):
    """Search modules!"""
    strings = {
        "name": "Limoka"
    }

    # maybe in future
    strings_ru = {"hello": "Привет мир!"}

    async def get_all_modules(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://limoka.vsecoder.dev/api/module/all') as response:
                return response.json()
    
    def search_by_description(self, query: str, descriptions: str) -> dict:
        pass

    def search_by_name(self, query: str, names: str):
        pass

    def search_by_commands(self, query: str, commands: list): # WARNING! COMMANDS IS LIST!  
        pass

    @loader.command()
    async def lsearch(self, message: Message):
        """ [query] - Search module"""
        args = utils.get_args.raw(message)

        modules = await self.get_all_modules()

        for module in modules:
            description = self.search_by_description(args, module["description"])
            name = self.search_by_name(args, module["name"])
            commands = self.search_by_commands(args, module["commands"])
