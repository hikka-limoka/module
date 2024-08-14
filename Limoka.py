import aiohttp
from rapidfuzz import fuzz
import random
from difflib import SequenceMatcher
import logging

from hikkatl.types import Message
from .. import utils, loader


# meta developer: @limokanews
# requires: rapidfuzz

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
        "found": "<emoji document_id=5411608069396254249>❤️</emoji> Found the module <b>{name}</b> by query: <b>{query}</b>"
                 "\n<emoji document_id=5411328862162276081>❤️</emoji> <b>Description:</b> {description}"
                 "\n<emoji document_id=5413534280624134677>❤️</emoji> <b>Hash:</b> <code>{hash}</code>"
                 "\n<emoji document_id=5418005479018221042>❤️</emoji> <b>Downloads:</b> <code>{downloads}</code>"
                 "\n<emoji document_id=5411143117711624172>❤️</emoji> <b>Views:</b> <code>{looks}</code>"
                 "\n\n<emoji document_id=5413350219800661019>❤️</emoji> <b>Commands:</b> \n{commands}"
                 "\n\n<emoji document_id=5416085714536255830>❤️</emoji> <b>Developer:</b> @{username}"
                 "\n\n<emoji document_id=5413394354884596702>❤️</emoji> <b>Download:</b> <code>{prefix}dlm {link}</code>"
                 "\n\n<emoji document_id=5420492071809074249>❤️</emoji> <b>Found by: {reason}<b>",
        "command_template": "{emoji} <code>{prefix}{command}</code> - {description}",
        "emojis": {
            1: "<emoji document_id=5359539923168796233>⬜️</emoji>",
            2: "<emoji document_id=5359826595055935572>⬜️</emoji>",
            3: "<emoji document_id=5359582662388358786>⬜️</emoji>",
            4: "<emoji document_id=5368501355252031261>⬜️</emoji>",
            5: "<emoji document_id=5368714084982203985>⬜️</emoji>",
            6: "<emoji document_id=5224196617384503334>◽️</emoji>"
        }
    }

    # maybe in future ru

    async def client_ready(self, client, db):
        self._prefix = self.get_prefix()

    def __init__(self):
        self.api = LimokaAPI()
        self.facts = [
            "The limoka catalog is carefully moderated!", 
            "Limoka performance allows you to search for modules quickly!"
        ]
        
    
    def search_by_description(self, query: str, description: str, module_id: int) -> dict:
        match = fuzz.ratio(query, description)
        if match > 0.3:
            match = 0
        return {"id": module_id, "match": match, "type": "description"}
            

    def search_by_name(self, query: str, name: str, module_id: int):
        match = fuzz.ratio(query, name)
        if match > 0.3:
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

        dev_username = module_info["developer"]

        name = module_info["name"]

        commands = []

        command_count = 0
        for command in module_info["commands"]:
            command_count += 1
            if command_count < 6:
                commands.append(
                    self.strings["command_template"].format(
                        prefix=self._prefix,
                        command=command['command'],
                        emoji=self.strings['emojis'][command_count],
                        description=command["description"]
                    )
                )
                
            
            await utils.answer(
                message,
                self.strings["found"].format(
                    query=args,
                    name=module_info["name"],
                    description=module_info["description"],
                    hash=module_info["hash"],
                    looks=len(module_info["looks"]),
                    downloads=len(module_info["downloads"]),
                    username=dev_username,
                    commands='\n'.join(commands),
                    prefix=self._prefix,
                    link=f"https://limoka.vsecoder.dev/api/module/{dev_username}/{name}.py",
                    reason=most_matches[0]["type"]
                )
            )