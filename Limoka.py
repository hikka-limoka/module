import aiohttp
import tempfile
import os
import random
from difflib import SequenceMatcher
import logging

from hikkatl.types import Message
from .. import utils, loader


# meta developer: @limokanews

logger = logging.getLogger("Limoka")

class LimokaAPI:
    async def get_all_modules(self) -> list:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://limoka.vsecoder.dev/api/module/all') as response:
                # A necessary crutch, because the server 
                # returns a list, but aiohttp gives only json
                return [await response.json()][0] 
            
    async def get_module_by_id(self, id) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://limoka.vsecoder.dev/api/module/{id}') as response:
                return await response.json()
            
    async def get_module_raw(self, developer, module_name) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://limoka.vsecoder.dev/api/module/{developer}/{module_name}') as response:
                return {"content": response.content(), "name": f"{module_name}.py"}
                

@loader.tds
class Limoka(loader.Module):
    """Search modules!"""
    strings = {
        "name": "Limoka",
        "wait": "Just wait"
                "\n<i>{fact}</i>",
        "found": "Found the module <b>{name}</b> by query: <b>{query}</b>"
                 "\n<b>Description:</b> {description}"
                 "\n\n<b>Developer:</b> @{username}"
                 "\n\n<b>Commands:</b> {commands}"
                 "\n\n<b>Download:</b> <code>{prefix}dlm {link}</code>",
        "command_template": "<code>{prefix}{command}</code> - {description}"
    }

    # maybe in future
    strings_ru = {"hello": "Привет мир!"}

    async def client_ready(self, client, db):
        self._prefix = self.get_prefix()

    def __init__(self):
        self.api = LimokaAPI()
        self.facts = [
            "The limoka catalog is carefully moderated!", 
            "Limoka performance allows you to search for modules quickly!"
        ]
        
    
    def search_by_description(self, query: str, description: str, module_id: int) -> dict:
        matcher = SequenceMatcher(None, query, description)
        match = matcher.ratio()
        if match > 0.5:
            match = 0
        return {"id": module_id, "match": match, "type": "description"}
            

    def search_by_name(self, query: str, name: str, module_id: int):
        matcher = SequenceMatcher(None, query, name)
        match = matcher.ratio()
        if match > 0.5:
            match = 0
        return {"id": module_id, "match": match, "type": "name"}
    
    def search_by_commands(self, query: str, commands: list, module_id: int): # Temporiary disabled
        if len(commands) == [0,1]:
            matcher = SequenceMatcher(None, query, commands[0]["command"])
            match = matcher.ratio()
        else:
            matches = 0
            for command in commands:
                matcher = SequenceMatcher(None, query, command["command"])
                matches += matcher.ratio()
            
            logger.info(commands)
            match = matches / len(commands)

        return {"id": module_id, "match": match, "type": "command"}

    @loader.command()
    async def lsearch(self, message: Message):
        """ [query] - Search module"""
        args = utils.get_args_raw(message)

        await utils.answer(
            message,
            self.strings["wait"].format(
                fact=random.choice(self.facts)
            )      
        )

        modules = await self.api.get_all_modules()

        matches = []

        for module in modules:
            description_match = self.search_by_description(args, module["description"], module["id"])
            name_match = self.search_by_name(args, module["name"], module["id"])
            #commands_match = self.search_by_commands(args, module["commands"], module["id"])

            matches.append(description_match)
            matches.append(name_match)
            #matches.append(commands_match)

        most_matches = sorted(matches, key=lambda x: x["match"])

        module_id = most_matches[0]["id"]
        module_info = await self.api.get_module_by_id(module_id)

        # Temporary crutch, because there 
        # is no username in the api
        dev_username = (await self.client.get_entity(int(module_info["developer"]))).username

        if dev_username == None:
            dev_username = (await self.client.get_entity(int(module_info["developer"]))).usernames[0].username

        name = module_info["name"]

        commands = []

        for command in module_info["commands"]:
            commands.append(
                self.strings["command_template"].format(
                    prefix=self._prefix,
                    command=command["command"],
                    description=command["description"]
                )
            )

            await utils.answer(
                message,
                self.strings["found"].format(
                    query=args,
                    name=module_info["name"],
                    description=module_info["description"],
                    username=dev_username,
                    commands='\n'.join(commands),
                    prefix=self._prefix,
                    link=f"https://limoka.vsecoder.dev/api/module/{dev_username}/{name}.py"
                )
            )