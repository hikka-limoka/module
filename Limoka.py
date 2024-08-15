from whoosh.index import create_in
from whoosh.fields import TEXT, ID, Schema
from whoosh.qparser import QueryParser, OrGroup
from whoosh.query import FuzzyTerm, Wildcard

import aiohttp
import random
import logging
import os
import shutil

from hikkatl.types import Message
from .. import utils, loader


# meta developer: @limokanews
# requires: whoosh

logger = logging.getLogger("Limoka")

class Search:
    def __init__(self, query: str):
        self.schema = Schema(title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True))
        self.query = query

    def search_module(self, content):
        if not os.path.exists("limoka_search"):
            os.makedirs("limoka_search")
        
        ix = create_in("limoka_search", self.schema)
        writer = ix.writer()
        module_count = 0
        for module_content in content:
            module_count += 1
            writer.add_document(
                title=f"{module_content['id']}", 
                path=f"{module_count}",
                content=module_content["content"]
            )
        writer.commit()

        with ix.searcher() as searcher:

            parser = QueryParser("content", ix.schema, group=OrGroup)
            query = parser.parse(self.query)

            # Пример добавления нечёткого поиска
            fuzzy_query = FuzzyTerm("content", self.query, maxdist=1, prefixlength=2)

            # Пример использования побуквенного поиска (Wildcard)
            wildcard_query = Wildcard("content", f"*{self.query}*")

            results = searcher.search(query)

            if not results:
                results = searcher.search(fuzzy_query)
            if not results:
                results = searcher.search(wildcard_query)

            if results:
                best_match = results[0]
                return int(best_match["title"])
            else:
                return 0


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
                 "\n<emoji document_id=5416085714536255830>❤️</emoji> <b>Developer:</b> @{username}"
                 "\n\n<emoji document_id=5413394354884596702>❤️</emoji> <b>Download:</b> <code>{prefix}dlm {link}</code>",
        "command_template": "{emoji} <code>{prefix}{command}</code> - {description}",
        "emojis": {
            1: "<emoji document_id=5359539923168796233>⬜️</emoji>",
            2: "<emoji document_id=5359826595055935572>⬜️</emoji>",
            3: "<emoji document_id=5359582662388358786>⬜️</emoji>",
            4: "<emoji document_id=5368501355252031261>⬜️</emoji>",
            5: "<emoji document_id=5368714084982203985>⬜️</emoji>",
            6: "<emoji document_id=5224196617384503334>◽️</emoji>"
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> Not found"
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

    @loader.command()
    async def limoka(self, message: Message):
        """ [query] - Search module"""
        args = utils.get_args_raw(message)

        await utils.answer(
            message,
            self.strings["wait"].format(
                fact=random.choice(self.facts)
            )      
        )

        modules = await self.api.get_all_modules()

        contents = []

        for module in modules:
            contents.append(
                {
                    "id": module["id"], 
                    "content": module["name"],
                }
            )

        for module in modules:
            contents.append(
                {
                    "id": module["id"], 
                    "content": module["description"],
                }
            )

        for module in modules:
            for command in module["commands"]:
                contents.append(
                    {
                        "id": module["id"],
                        "content": command["command"]
                    }
                )
                contents.append(
                    {
                        "id": module["id"],
                        "content": command["description"]
                    }
                )

        searcher = Search(args)
        result = searcher.search_module(contents)

        module_id = result

        if module_id == 0:
            await utils.answer(message, self.strings["404"])

        else:

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
                else:
                    commands.append("...")
                    
                
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
                        commands=''.join(commands),
                        prefix=self._prefix,
                        link=f"https://limoka.vsecoder.dev/api/module/{dev_username}/{name}.py",
                    )
                )