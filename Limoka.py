from whoosh.index import create_in
from whoosh.fields import TEXT, ID, Schema
from whoosh.qparser import QueryParser, OrGroup
from whoosh.query import FuzzyTerm, Wildcard

import aiohttp
import random
import logging
import os
import re
import html

from telethon.types import Message
from telethon.errors.rpcerrorlist import YouBlockedUserError
from ..inline.types import InlineCall
from .. import utils, loader


# meta developer: @limokanews
# requires: whoosh

logger = logging.getLogger("Limoka")
    
class Search:
    def __init__(self, query: str):
        self.schema = Schema(title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True))
        self.query = query
        self.base_url = "http://123.123.123.123"

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

            fuzzy_query = FuzzyTerm("content", self.query, maxdist=1, prefixlength=2)

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
            async with session.get(f'{self.base_url}api/module/all') as response:
                # A necessary crutch, because the server 
                # returns a list, but aiohttp gives only json
                return [await response.json()][0] 
            
    async def get_module_by_id(self, id) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{self.base_url}api/module/{id}') as response:
                return await response.json()
            
    async def get_module_raw(self, developer, module_name) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{self.base_url}api/module/{developer}/{module_name}') as response:
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
                 "\n<b>Hash:</b> <code>{hash}</code>"
                 "\n<b>Downloads:</b> <code>{downloads}</code>"
                 "\n<b>Views:</b> <code>{looks}</code>"
                 "\n\n<b>Commands:</b> \n{commands}"
                 "\n<b>Developer:</b> @{username}",
        "command_template": "{emoji} <code>{prefix}{command}</code> - {description}",
        "emojis": {
            1: "<emoji document_id=5449498872176983423>1️⃣</emoji>",
            2: "<emoji document_id=5447575603001705541>2️⃣</emoji>",
            3: "<emoji document_id=5447344971847844130>3️⃣</emoji>",
            4: "<emoji document_id=5449783211896879221>4️⃣</emoji>",
            5: "<emoji document_id=5449556257235024153>5️⃣</emoji>",
            6: "<emoji document_id=5449643483725837995>6️⃣</emoji>",
            7: "<emoji document_id=5447255791146910115>7️⃣</emoji>",
            8: "<emoji document_id=5449394534536462346>8️⃣</emoji>",
            9: "<emoji document_id=5447140424030371281>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Not found</b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>No args</b>",
        "?": "Request too short / not found"
    }

    strings_ru = {
        "wait": "Подождите"
                "\n<i>{fact}</i>",
        "found": "Найден модуль <b>{name}</b> по запросу: <b>{query}</b>"
                 "\n<b>Описание:</b> {description}"
                 "\n<b>Хэш:</b> <code>{hash}</code>"
                 "\n<b>Загрузок:</b> <code>{downloads}</code>"
                 "\n<b>Просмотров:</b> <code>{looks}</code>"
                 "\n\n<b>Команды:</b> \n{commands}"
                 "\n<b>Разработчик:</b> @{username}",
        "command_template": "{emoji} <code>{prefix}{command}</code> - {description}",
        "emojis": {
            1: "<emoji document_id=5449498872176983423>1️⃣</emoji>",
            2: "<emoji document_id=5447575603001705541>2️⃣</emoji>",
            3: "<emoji document_id=5447344971847844130>3️⃣</emoji>",
            4: "<emoji document_id=5449783211896879221>4️⃣</emoji>",
            5: "<emoji document_id=5449556257235024153>5️⃣</emoji>",
            6: "<emoji document_id=5449643483725837995>6️⃣</emoji>",
            7: "<emoji document_id=5447255791146910115>7️⃣</emoji>",
            8: "<emoji document_id=5449394534536462346>8️⃣</emoji>",
            9: "<emoji document_id=5447140424030371281>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не найдено</b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>Нет аргументов</b>",
        "?": "Запрос слишком короткий / не найден"
    }

    async def client_ready(self, client, db):
        self._prefix = self.get_prefix()

    def __init__(self):
        self.api = LimokaAPI()
        self.facts = [
            "The limoka catalog is carefully moderated!", 
            "Limoka performance allows you to search for modules quickly!"
        ]
        self.BOT = 7059081890

    async def buttons_download(self, module_id, url, text, message: Message):
        markup = [
            {
                "text": "⬇️ Download",
                "callback": self._inline_download,
                "args": [url, module_id]
            }
        ]

        return await self.inline.form(
            text,
            message,
            reply_markup=markup,
        )

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

        if not args:
            return await utils.answer(message, self.strings["noargs"])

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
            for func in module["commands"]:
                for command, description in func.items():
                    contents.append(
                        {
                            "id": module["id"],
                            "content": command
                        }
                    )
                    contents.append(
                        {
                            "id": module["id"],
                            "content": description
                        }
                    )

        searcher = Search(args)
        try:
            result = searcher.search_module(contents)
        except IndexError:
            return await utils.answer(message, self.strings["?"]) 

        module_id = result

        if module_id == 0:
            await utils.answer(message, self.strings["404"])

        else:

            module_info = await self.api.get_module_by_id(module_id)

            dev_username = module_info["developer"]

            name = module_info["name"]

            commands = []

            command_count = 0
            for func in module_info["commands"]:
                for command, description in func.items():
                    command_count += 1
                    if command_count < 9:
                        commands.append(
                            self.strings["command_template"].format(
                                prefix=self._prefix,
                                command=html.escape(command),
                                emoji=self.strings['emojis'][command_count],
                                description=html.escape(description)
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