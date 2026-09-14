"""Reading a whole paged list in a test — Story A-13.

Most story tests are about *what is in* a list ("all 18 league clubs appear"), not about
how much of it fits on one page. Since the list endpoints answer 25 rows at a time, those
tests have to page, and doing that by hand at each call site is how a test ends up
asserting against page one and passing for the wrong reason: it only breaks once the suite
has created enough rows to push the row it looks for onto page two, which is a failure that
shows up in an unrelated commit.
"""

from typing import Any

#: The server's own cap. Asking for more is a 422, so the walk goes in these steps.
MAX_LIMIT = 100


async def all_items(client, path: str, **kwargs: Any) -> list[dict]:
    """Every row of a paged list, following the pages to the end."""
    params = dict(kwargs.pop("params", None) or {})
    rows: list[dict] = []
    offset = 0
    while True:
        query = {**params, "limit": MAX_LIMIT, "offset": offset}
        page = (await client.get(path, params=query, **kwargs)).json()
        rows.extend(page["items"])
        offset += MAX_LIMIT
        if offset >= page["total"]:
            return rows
