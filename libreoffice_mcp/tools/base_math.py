"""Base (database) and Math (formula) tools."""
import os

from .. import bridge as b
from ._util import enum

_conns = {}


def _conn(doc_id):
    if doc_id not in _conns:
        m = b.need(doc_id, "base")
        _conns[doc_id] = m.getDataSource().getConnection("", "")
    return _conns[doc_id]


def base_create(path: str) -> dict:
    """Create a new embedded Base database file (.odb) and open it."""
    ctx = b.create("com.sun.star.sdb.DatabaseContext")
    ds = ctx.createInstance()
    ds.URL = "sdbc:embedded:firebird"
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(path))), exist_ok=True)
    url = b.to_url(path)
    ds.DatabaseDocument.storeAsURL(url, ())
    return base_open(path)


def base_open(path: str) -> dict:
    """Open an existing .odb database and return a doc_id."""
    m = b.desktop().loadComponentFromURL(b.to_url(path), "_blank", 0, b.props(Hidden=True))
    if m is None:
        raise b.LOError(f"Cannot open {path}")
    return {"doc_id": b.register_doc(m), "kind": b.doc_kind(m)}


def base_tables(doc_id: str) -> list:
    """List tables and their columns."""
    c = _conn(doc_id)
    t = c.getTables()
    return [{"table": n, "columns": [{"name": col, "type": t.getByName(n).getColumns().getByName(col).TypeName} for col in t.getByName(n).getColumns().ElementNames]}
            for n in t.ElementNames]


def base_query(doc_id: str, sql: str, limit: int = 200) -> dict:
    """Run a SELECT and return columns + rows (up to limit)."""
    st = _conn(doc_id).createStatement()
    rs = st.executeQuery(sql)
    md = rs.getMetaData()
    cols = [md.getColumnName(i) for i in range(1, md.getColumnCount() + 1)]
    rows = []
    while rs.next() and len(rows) < limit:
        rows.append([rs.getObject(i, None) if False else rs.getString(i) for i in range(1, len(cols) + 1)])
    return {"columns": cols, "rows": rows}


def base_execute(doc_id: str, sql: str) -> dict:
    """Run INSERT/UPDATE/DELETE/CREATE/DROP and persist the change."""
    c = _conn(doc_id)
    n = c.createStatement().executeUpdate(sql)
    b.doc(doc_id).store()
    return {"affected": n}


def math_set_formula(doc_id: str, formula: str) -> dict:
    """Set the formula in a Math document (StarMath syntax, e.g. 'x = {-b +- sqrt{b^2 - 4ac}} over {2a}')."""
    m = b.need(doc_id, "math")
    m.setPropertyValue("Formula", formula)
    return {"formula": m.getPropertyValue("Formula")}


def math_insert_into(doc_id: str, formula: str) -> dict:
    """Embed a formula object at the end of a Writer document."""
    m = b.need(doc_id, "writer")
    t = m.getText()
    obj = m.createInstance("com.sun.star.text.TextEmbeddedObject")
    obj.setPropertyValue("CLSID", "078B7ABA-54FC-457F-8551-6147e776a997")
    obj.setPropertyValue("AnchorType", enum("com.sun.star.text.TextContentAnchorType", "AS_CHARACTER"))
    c = t.createTextCursor()
    c.gotoEnd(False)
    t.insertTextContent(c, obj, False)
    obj.getEmbeddedObject().setPropertyValue("Formula", formula)
    return {"ok": True}


TOOLS = [base_create, base_open, base_tables, base_query, base_execute, math_set_formula, math_insert_into]
