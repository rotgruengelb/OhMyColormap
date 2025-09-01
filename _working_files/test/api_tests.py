import dotenv

from util.modrinth.api import ModrinthAPI

modrinth = ModrinthAPI(
    token=dotenv.get_key("../.env", "MODRINTH_TOKEN"),
    user_agent="Pridecraft-Studios/pridetooltips testing"
)
print(modrinth.get_project("fresh-animations"))