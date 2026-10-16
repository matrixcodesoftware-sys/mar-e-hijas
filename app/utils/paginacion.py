"""Paginación del lado del servidor."""
import math
from urllib.parse import urlencode

from flask import current_app, request

from ..database import query, scalar


class Pagina:
    def __init__(self, items, total, pagina, por_pagina):
        self.items = items
        self.total = int(total or 0)
        self.pagina = pagina
        self.por_pagina = por_pagina
        self.paginas = max(1, math.ceil(self.total / por_pagina)) if por_pagina else 1

    @property
    def tiene_anterior(self):
        return self.pagina > 1

    @property
    def tiene_siguiente(self):
        return self.pagina < self.paginas

    def url(self, numero):
        args = request.args.to_dict()
        args["pagina"] = numero
        return request.path + "?" + urlencode(args)

    def rango(self, ventana=2):
        ini = max(1, self.pagina - ventana)
        fin = min(self.paginas, self.pagina + ventana)
        return range(ini, fin + 1)


def pagina_actual():
    try:
        return max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        return 1


def paginar(sql_select, sql_from_where, params, orden, pagina=None, por_pagina=None):
    """sql_select: 'SELECT a, b'  ·  sql_from_where: 'FROM … WHERE …'  ·  orden: 'ORDER BY …'."""
    pagina = pagina or pagina_actual()
    por_pagina = por_pagina or current_app.config["ITEMS_POR_PAGINA"]
    total = scalar(f"SELECT COUNT(*) AS n {sql_from_where}", params, 0)
    items = query(
        f"{sql_select} {sql_from_where} {orden} LIMIT %s OFFSET %s",
        list(params) + [por_pagina, (pagina - 1) * por_pagina],
    )
    return Pagina(items, total, pagina, por_pagina)
