"""How a list is narrowed and ordered — one base class over `fastapi-filter` (Story A-13,
decided 2026-10-25).

Every paged list declares a :class:`ListFilter` subclass: its search (``q``), its sort
(``sort``, from a whitelist of columns) and its filters, each a typed field — so FastAPI
lists every one of them as a query parameter, the generated client knows them by name and
type, and a wrong type is a 422 at validation. The route takes it with
``filters: EventFilter = ListDepends(EventFilter)`` and runs
``filters.sort(filters.filter(stmt))`` before :func:`app.pagination.paginate`, which only
counts and cuts.

`fastapi-filter` brings the typed fields, the Django-style operators (``starts_on__gte``,
``status__in`` as ``?status__in=live,final``) and the dependency that turns a query string
into the model. This class adds the rules the project already had, where the library is
looser:

* **Only a declared column sorts** (``Constants.sortable``), refused with the
  ``unknown-sort-column`` problem naming what would have been accepted — the library alone
  sorts by any attribute of the model, relationships included.
* **A blank search is no search** (`app.pagination.apply_search`): the library would match
  ``%   %`` and drop every row whose searched columns are NULL. A search that needs joins
  overrides :meth:`search`.
* **A filter with a meaning of its own** — "a series' posts, its events' too" — is a
  method ``where_<field>(value)`` returning its clause, or ``None`` for "no filter"; the
  library's own operators handle the rest.
* **Text sorts regardless of case** — ``lower()`` of a string column: SQLite's own
  order puts every lowercase name after ``Z``, which no reader expects (#47).
* **The default order is the tie-break**, appended after the requested sort, so equal rows
  never wander between pages.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from fastapi_filter import FilterDepends
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import ValidationInfo, field_validator
from sqlalchemy import Select, String, func

from app.pagination import apply_search
from app.problems import Problem

__all__ = ["ListDepends", "ListFilter"]


def ListDepends(filter_class: type[ListFilter]):  # noqa: N802 — a FastAPI dependency
    """The dependency a route takes its list's filter with — by alias, so ``?sort=``
    reaches the ``order_by`` field."""
    return FilterDepends(filter_class, by_alias=True)


class ListFilter(Filter):
    """The project's list filter. A subclass sets ``Constants.model``, ``sortable``,
    ``default_order`` and ``search_columns``, and declares ``q``, ``sort`` and its
    filters as optional fields."""

    class Constants(Filter.Constants):
        #: The field; its query parameter is ``sort`` (an alias — see `app/filters.py`).
        ordering_field_name = "order_by"
        search_field_name = "q"
        #: The columns ``sort`` accepts, by the name a caller uses.
        sortable: ClassVar[Mapping[str, Any]] = {}
        #: The order of equal rows — and of every row when no sort is asked for.
        default_order: ClassVar[tuple[Any, ...]] = ()
        #: What ``q`` searches, unless :meth:`search` is overridden.
        search_columns: ClassVar[tuple[Any, ...]] = ()

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value: Any, field: ValidationInfo) -> Any:  # noqa: N805
        """Replaces the library's check (same name, so it is overridden): only a declared
        column, and the refusal names the ones that are."""
        if field.field_name != cls.Constants.ordering_field_name:
            return value
        if not value:
            return None
        for name in value:
            column = name.strip().lstrip("+-")
            if column not in cls.Constants.sortable:
                raise Problem(
                    status=422,
                    code="unknown-sort-column",
                    title=f"Cannot sort by {column!r}.",
                    column=column,
                    sortable=sorted(cls.Constants.sortable),
                )
        return value

    def search(self, stmt: Select, q: str | None) -> Select:
        """What ``q`` means for this list — its columns, case-insensitively, anywhere."""
        return apply_search(stmt, q, *self.Constants.search_columns)

    def filter(self, query: Select) -> Select:  # type: ignore[override]
        """The search, the filters with a meaning of their own, then the library's operators
        for the rest."""
        fields = type(self).model_fields
        handled = {self.Constants.ordering_field_name}
        if self.Constants.search_field_name in fields:
            query = self.search(query, getattr(self, self.Constants.search_field_name))
            handled.add(self.Constants.search_field_name)
        for name in fields:
            where = getattr(self, f"where_{name}", None)
            if where is None:
                continue
            handled.add(name)
            value = getattr(self, name)
            clause = where(value) if value is not None else None
            if clause is not None:
                query = query.where(clause)
        rest = self.model_copy(update={name: None for name in handled})
        return Filter.filter(rest, query)

    def sort(self, query: Select) -> Select:  # type: ignore[override]
        """The requested order — then the default one, as the tie-break."""
        order = []
        for name in self.ordering_values or []:
            column = self.Constants.sortable[name.strip().lstrip("+-")]
            if isinstance(getattr(column, "type", None), String):
                column = func.lower(column)
            order.append(column.desc() if name.strip().startswith("-") else column.asc())
        return query.order_by(*order, *self.Constants.default_order)
