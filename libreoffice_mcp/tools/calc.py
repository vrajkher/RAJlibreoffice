"""Calc (spreadsheet) tools. Ranges use A1 notation, optionally sheet-qualified: 'Sheet1.A1:C10'."""
import uno

from .. import bridge as b
from ._util import ALIGN, color, enum, struct

C = ("calc",)
MAX_CELLS = 20000


def _sheet(m, name=""):
    sh = m.getSheets()
    if name:
        if not sh.hasByName(name):
            raise b.LOError(f"No sheet '{name}'. Sheets: {list(sh.ElementNames)}")
        return sh.getByName(name)
    return m.getCurrentController().getActiveSheet() if m.getCurrentController() else sh.getByIndex(0)


def _split(ref, sheet):
    """Return (sheet_name, local_ref) from 'Sheet1.A1:B2' or ('', 'A1:B2')."""
    ref = ref.replace("$", "")
    if "." in ref:
        sn, _, rest = ref.rpartition(".") if ":" not in ref else (ref.split(":")[0].rpartition(".")[0], None, None)
        if ":" in ref:
            first, _, last = ref.partition(":")
            sn, _, a = first.rpartition(".")
            return sn.strip("'"), f"{a}:{last.rpartition('.')[2]}"
        return sn.strip("'"), rest
    return sheet, ref


def _rng(doc_id, ref, sheet=""):
    m = b.need(doc_id, *C)
    sn, local = _split(ref, sheet)
    return m, _sheet(m, sn).getCellRangeByName(local)


def calc_sheets(doc_id: str) -> list:
    """List sheets with their used areas."""
    m = b.need(doc_id, *C)
    out = []
    for n in m.getSheets().ElementNames:
        s = m.getSheets().getByName(n)
        cur = s.createCursor()
        cur.gotoEndOfUsedArea(False)
        out.append({"name": n, "rows": cur.RangeAddress.EndRow + 1, "cols": cur.RangeAddress.EndColumn + 1, "visible": s.IsVisible})
    return out


def calc_sheet_edit(doc_id: str, action: str, name: str, new_name: str = "", index: int = -1) -> dict:
    """action: add | delete | rename | copy | move | hide | show. `index` is the 0-based position for add/copy/move."""
    m = b.need(doc_id, *C)
    sh = m.getSheets()
    n = sh.getCount()
    pos = n if index < 0 else index
    if action == "add":
        sh.insertNewByName(name, pos)
    elif action == "delete":
        sh.removeByName(name)
    elif action == "rename":
        sh.getByName(name).setName(new_name)
    elif action == "copy":
        sh.copyByName(name, new_name, pos)
    elif action == "move":
        sh.moveByName(name, pos)
    elif action in ("hide", "show"):
        sh.getByName(name).setPropertyValue("IsVisible", action == "show")
    else:
        raise b.LOError("action must be add|delete|rename|copy|move|hide|show")
    return {"sheets": list(sh.ElementNames)}


def calc_get_range(doc_id: str, range: str, sheet: str = "", formulas: bool = False) -> dict:
    """Read a range as a 2D list. formulas=True returns formulas ('=SUM(A1:A3)') instead of computed values."""
    _, r = _rng(doc_id, range, sheet)
    a = r.RangeAddress
    if (a.EndRow - a.StartRow + 1) * (a.EndColumn - a.StartColumn + 1) > MAX_CELLS:
        raise b.LOError(f"Range too large (>{MAX_CELLS} cells); read it in chunks.")
    data = r.getFormulaArray() if formulas else r.getDataArray()
    return {"range": range, "data": [list(row) for row in data]}


def calc_set_range(doc_id: str, start: str, values: list, sheet: str = "") -> dict:
    """Write a 2D list starting at `start` (e.g. 'B2'). Numbers stay numbers; strings starting with '=' are formulas; None leaves '' ."""
    m = b.need(doc_id, *C)
    sn, local = _split(start, sheet)
    s = _sheet(m, sn)
    rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in values]
    width = max(len(r) for r in rows)
    c0 = s.getCellRangeByName(local.split(":")[0])
    ca = c0.CellAddress if hasattr(c0, "CellAddress") else c0.RangeAddress
    col, row = (ca.Column, ca.Row) if hasattr(ca, "Column") else (ca.StartColumn, ca.StartRow)
    tgt = s.getCellRangeByPosition(col, row, col + width - 1, row + len(rows) - 1)
    tgt.setFormulaArray(tuple(tuple(("" if v is None else (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v))) for v in (r + [None] * (width - len(r)))) for r in rows))
    return {"written": f"{len(rows)}x{width}", "at": start}


def calc_set_cell(doc_id: str, cell: str, value: object, sheet: str = "") -> dict:
    """Set one cell: number, text, bool, or '=formula'."""
    _, c = _rng(doc_id, cell, sheet)
    if isinstance(value, bool):
        c.setValue(1.0 if value else 0.0)
    elif isinstance(value, (int, float)):
        c.setValue(value)
    elif isinstance(value, str) and value.startswith("="):
        c.setFormula(value)
    else:
        c.setString("" if value is None else str(value))
    return {"ok": True, "value": c.getValue() if c.getType().value in ("VALUE", "FORMULA") else c.getString()}


def calc_clear(doc_id: str, range: str, sheet: str = "", what: str = "all") -> dict:
    """Clear contents. what: all | values | formulas | formats | text."""
    _, r = _rng(doc_id, range, sheet)
    flags = {"all": 1023, "values": 1, "text": 4, "formulas": 16, "formats": 512}[what]  # CellFlags
    r.clearContents(flags)
    return {"ok": True}


def calc_format_range(doc_id: str, range: str, sheet: str = "", bold: bool = None, italic: bool = None, underline: bool = None,
                      size: float = None, font: str = None, color_fg: str = None, color_bg: str = None, align: str = None,
                      valign: str = None, wrap: bool = None, number_format: str = None, borders: bool = None, border_color: str = "#000000",
                      rotation: int = None, indent: int = None) -> dict:
    """Format cells. number_format examples: '0.00', '#,##0', '0%', 'YYYY-MM-DD', '$#,##0.00', '@'. align: left|center|right|justify. valign: top|center|bottom."""
    m, r = _rng(doc_id, range, sheet)
    p = {}
    if bold is not None: p["CharWeight"] = 150.0 if bold else 100.0
    if italic is not None: p["CharPosture"] = enum("com.sun.star.awt.FontSlant", "ITALIC" if italic else "NONE")
    if underline is not None: p["CharUnderline"] = 1 if underline else 0
    if size is not None: p["CharHeight"] = float(size)
    if font: p["CharFontName"] = font
    if color_fg is not None: p["CharColor"] = color(color_fg)
    if color_bg is not None: p["CellBackColor"] = color(color_bg)
    if align: p["HoriJustify"] = enum("com.sun.star.table.CellHoriJustify", {"left": "LEFT", "center": "CENTER", "right": "RIGHT", "justify": "BLOCK"}[align])
    if valign: p["VertJustify"] = enum("com.sun.star.table.CellVertJustify", valign.upper())
    if wrap is not None: p["IsTextWrapped"] = wrap
    if rotation is not None: p["RotateAngle"] = rotation * 100
    if indent is not None: p["ParaIndent"] = indent
    if number_format:
        fmts = m.getNumberFormats()
        loc = struct("com.sun.star.lang.Locale", Language="en", Country="US")
        key = fmts.queryKey(number_format, loc, False)
        p["NumberFormat"] = key if key != -1 else fmts.addNew(number_format, loc)
    for k, v in p.items():
        r.setPropertyValue(k, v)
    if borders:
        line = struct("com.sun.star.table.BorderLine2", Color=color(border_color), OuterLineWidth=26, LineWidth=26)
        tb = r.getPropertyValue("TableBorder2")
        for side in ("TopLine", "BottomLine", "LeftLine", "RightLine", "HorizontalLine", "VerticalLine"):
            setattr(tb, side, line)
            setattr(tb, "Is" + side[:-4] + "LineValid", True) if hasattr(tb, "Is" + side[:-4] + "LineValid") else None
        r.setPropertyValue("TableBorder2", tb)
    return {"ok": True}


def calc_merge(doc_id: str, range: str, sheet: str = "", merge: bool = True) -> dict:
    """Merge or unmerge cells."""
    _, r = _rng(doc_id, range, sheet)
    r.merge(merge)
    return {"ok": True}


def calc_insert_delete(doc_id: str, action: str, index: int, count: int = 1, sheet: str = "") -> dict:
    """action: insert_rows | delete_rows | insert_cols | delete_cols (0-based index)."""
    m = b.need(doc_id, *C)
    s = _sheet(m, sheet)
    rc = s.getRows() if action.endswith("rows") else s.getColumns()
    (rc.insertByIndex if action.startswith("insert") else rc.removeByIndex)(index, count)
    return {"ok": True}


def calc_col_row_size(doc_id: str, kind: str, index: int, size_mm: float = None, optimal: bool = False, hidden: bool = None, count: int = 1, sheet: str = "") -> dict:
    """Resize columns/rows (kind: col | row). optimal=True autofits. 0-based index."""
    s = _sheet(b.need(doc_id, *C), sheet)
    rc = s.getColumns() if kind == "col" else s.getRows()
    for i in range(index, index + count):
        x = rc.getByIndex(i)
        if optimal: x.setPropertyValue("OptimalWidth" if kind == "col" else "OptimalHeight", True)
        if size_mm is not None: x.setPropertyValue("Width" if kind == "col" else "Height", int(size_mm * 100))
        if hidden is not None: x.setPropertyValue("IsVisible", not hidden)
    return {"ok": True}


def calc_freeze(doc_id: str, columns: int = 0, rows: int = 0) -> dict:
    """Freeze the first N columns/rows (0,0 unfreezes)."""
    c = b.need(doc_id, *C).getCurrentController()
    c.freezeAtPosition(columns, rows) if (columns or rows) else c.freezeAtPosition(0, 0)
    return {"ok": True}


def calc_named_range(doc_id: str, action: str, name: str = "", range: str = "", sheet: str = "") -> object:
    """action: add | list | delete. `range` like 'Sheet1.A1:B5'."""
    m = b.need(doc_id, *C)
    nr = m.NamedRanges
    if action == "list":
        return [{"name": n, "content": nr.getByName(n).getContent()} for n in nr.ElementNames]
    if action == "delete":
        nr.removeByName(name)
        return {"deleted": name}
    sn, local = _split(range, sheet)
    s = _sheet(m, sn)
    tgt = s.getCellRangeByName(local)
    pos = s.getCellRangeByName(local.split(":")[0]).CellAddress
    nr.addNewByName(name, tgt.AbsoluteName, pos, 0)
    return {"added": name}


def calc_sort(doc_id: str, range: str, column: int = 0, ascending: bool = True, has_header: bool = True, sheet: str = "") -> dict:
    """Sort a range by a column (0-based within the range)."""
    _, r = _rng(doc_id, range, sheet)
    f = struct("com.sun.star.table.TableSortField", Field=column, IsAscending=ascending, IsCaseSensitive=False)
    r.sort(b.props(SortFields=uno.Any("[]com.sun.star.table.TableSortField", (f,)), ContainsHeader=has_header))
    return {"ok": True}


def calc_autofilter(doc_id: str, range: str, enable: bool = True, sheet: str = "") -> dict:
    """Turn the AutoFilter dropdowns on/off for a range."""
    m, r = _rng(doc_id, range, sheet)
    dbs = m.DatabaseRanges
    name = "mcp_filter_" + range.replace(":", "_").replace(".", "_")
    if not dbs.hasByName(name):
        dbs.addNewByName(name, r.RangeAddress)
    dbs.getByName(name).setPropertyValue("AutoFilter", enable)
    return {"ok": True}


def calc_validation(doc_id: str, range: str, kind: str = "list", values: list = None, minimum: float = None, maximum: float = None,
                    sheet: str = "", message: str = "", error: str = "") -> dict:
    """Data validation. kind: list (values=[...]) | whole | decimal | date | textlength | custom (values=[formula]). min/max for numeric kinds."""
    _, r = _rng(doc_id, range, sheet)
    v = r.getPropertyValue("Validation")
    types = {"list": "LIST", "whole": "WHOLE", "decimal": "DECIMAL", "date": "DATE", "textlength": "TEXT_LEN", "custom": "CUSTOM"}
    v.setPropertyValue("Type", enum("com.sun.star.sheet.ValidationType", types[kind]))
    if kind == "list":
        v.setFormula1(";".join(f'"{x}"' for x in (values or [])))
    elif kind == "custom":
        v.setFormula1((values or [""])[0])
    else:
        op = "BETWEEN" if minimum is not None and maximum is not None else ("GREATER_EQUAL" if minimum is not None else "LESS_EQUAL")
        v.setOperator(enum("com.sun.star.sheet.ConditionOperator", op))
        v.setFormula1(str(minimum if minimum is not None else maximum))
        if op == "BETWEEN":
            v.setFormula2(str(maximum))
    v.setPropertyValue("ShowErrorMessage", bool(error))
    v.setPropertyValue("ErrorMessage", error)
    v.setPropertyValue("InputMessage", message)
    v.setPropertyValue("ShowInputMessage", bool(message))
    r.setPropertyValue("Validation", v)
    return {"ok": True}


def calc_conditional_format(doc_id: str, range: str, operator: str, value: object, value2: object = None,
                            bg: str = "#FFC7CE", fg: str = "#9C0006", bold: bool = None, sheet: str = "", formula: str = "") -> dict:
    """Highlight cells. operator: equal | not_equal | greater | greater_equal | less | less_equal | between | formula (then set `formula`)."""
    m, r = _rng(doc_id, range, sheet)
    styles = m.getStyleFamilies().getByName("CellStyles")
    sname = f"mcp_cf_{abs(hash((bg, fg, bold))) % 10**8}"
    if not styles.hasByName(sname):
        st = m.createInstance("com.sun.star.style.CellStyle")
        styles.insertByName(sname, st)
        st.setPropertyValue("CellBackColor", color(bg))
        st.setPropertyValue("CharColor", color(fg))
        if bold is not None:
            st.setPropertyValue("CharWeight", 150.0 if bold else 100.0)
    ops = {"equal": "EQUAL", "not_equal": "NOT_EQUAL", "greater": "GREATER", "greater_equal": "GREATER_EQUAL", "less": "LESS",
           "less_equal": "LESS_EQUAL", "between": "BETWEEN", "formula": "FORMULA"}
    cf = r.getPropertyValue("ConditionalFormat")
    pv = b.props(Operator=enum("com.sun.star.sheet.ConditionOperator", ops[operator]),
                 Formula1=formula if operator == "formula" else str(value), Formula2="" if value2 is None else str(value2), StyleName=sname)
    cf.addNew(pv)
    r.setPropertyValue("ConditionalFormat", cf)
    return {"style": sname}


def calc_chart(doc_id: str, data_range: str, kind: str = "column", title: str = "", anchor: str = "H2", width_mm: int = 140,
               height_mm: int = 80, name: str = "", sheet: str = "", first_row_header: bool = True, first_col_labels: bool = True) -> dict:
    """Create a chart from a range. kind: column | bar | line | pie | area | scatter | donut."""
    m, r = _rng(doc_id, data_range, sheet)
    s = r.Spreadsheet
    name = name or f"Chart{s.getCharts().getCount() + 1}"
    pos = s.getCellRangeByName(_split(anchor, sheet)[1]).Position
    rect = struct("com.sun.star.awt.Rectangle", X=pos.X, Y=pos.Y, Width=width_mm * 100, Height=height_mm * 100)
    s.getCharts().addNewByName(name, rect, (r.RangeAddress,), first_row_header, first_col_labels)
    ch = s.getCharts().getByName(name).getEmbeddedObject()
    svc = {"column": "BarDiagram", "bar": "BarDiagram", "line": "LineDiagram", "pie": "PieDiagram", "donut": "PieDiagram",
           "area": "AreaDiagram", "scatter": "XYDiagram"}[kind]
    d = ch.createInstance("com.sun.star.chart." + svc)
    ch.setDiagram(d)
    if kind in ("column", "bar"):
        d.setPropertyValue("Vertical", kind == "bar")
    if title:
        ch.setPropertyValue("HasMainTitle", True)
        ch.getTitle().setPropertyValue("String", title)
    return {"chart": name}


def calc_pivot(doc_id: str, source: str, dest_cell: str, rows: list, data: list, cols: list = None, function: str = "SUM",
               name: str = "Pivot1", sheet: str = "", dest_sheet: str = "") -> dict:
    """Create a pivot table. `source` has a header row; rows/cols/data are header names; function: SUM|COUNT|AVERAGE|MAX|MIN."""
    m, r = _rng(doc_id, source, sheet)
    s = _sheet(m, dest_sheet or _split(source, sheet)[0])
    tables = s.getDataPilotTables()
    desc = tables.createDataPilotDescriptor()
    desc.setSourceRange(r.RangeAddress)
    fields = desc.getDataPilotFields()
    O = "com.sun.star.sheet.DataPilotFieldOrientation"
    for lst, ori in ((rows, "ROW"), (cols or [], "COLUMN"), (data, "DATA")):
        for n in lst:
            f = fields.getByName(n)
            f.setPropertyValue("Orientation", enum(O, ori))
            if ori == "DATA":
                f.setPropertyValue("Function", enum("com.sun.star.sheet.GeneralFunction", function.upper()))
    tables.insertNewByName(name, s.getCellRangeByName(_split(dest_cell, "")[1]).CellAddress, desc)
    return {"pivot": name}


def calc_find_replace(doc_id: str, find: str, replace: str = None, sheet: str = "", regex: bool = False, match_case: bool = False, entire_cell: bool = False) -> dict:
    """Search (and optionally replace) in a sheet or the whole workbook (sheet='')."""
    m = b.need(doc_id, *C)
    targets = [_sheet(m, sheet)] if sheet else [m.getSheets().getByIndex(i) for i in range(m.getSheets().getCount())]
    total, hits = 0, []
    for s in targets:
        d = s.createReplaceDescriptor() if replace is not None else s.createSearchDescriptor()
        d.setSearchString(find)
        d.SearchRegularExpression, d.SearchCaseSensitive, d.SearchWords = regex, match_case, entire_cell
        if replace is not None:
            d.setReplaceString(replace)
            total += s.replaceAll(d)
        else:
            f = s.findAll(d)
            if f:
                total += f.getCount()
                hits += [f"{s.Name}.{f.getByIndex(i).AbsoluteName.split('.')[-1]}" for i in range(min(f.getCount(), 20))]
    return {"count": total, "cells": hits}


def calc_protect(doc_id: str, sheet: str, protect: bool = True, password: str = "") -> dict:
    """Protect/unprotect a sheet."""
    s = _sheet(b.need(doc_id, *C), sheet)
    (s.protect if protect else s.unprotect)(password)
    return {"protected": s.isProtected()}


def calc_recalculate(doc_id: str, hard: bool = False) -> dict:
    """Recalculate formulas (hard=True recalculates everything)."""
    m = b.need(doc_id, *C)
    m.calculateAll() if hard else m.calculate()
    return {"ok": True}


def calc_hyperlink(doc_id: str, cell: str, url: str, text: str = "", sheet: str = "") -> dict:
    """Put a clickable hyperlink in a cell."""
    m, c = _rng(doc_id, cell, sheet)
    f = m.createInstance("com.sun.star.text.TextField.URL")
    f.setPropertyValue("URL", url)
    f.setPropertyValue("Representation", text or url)
    c.getText().insertTextContent(c.getText().createTextCursor(), f, False)
    return {"ok": True}


TOOLS = [calc_sheets, calc_sheet_edit, calc_get_range, calc_set_range, calc_set_cell, calc_clear, calc_format_range, calc_merge,
         calc_insert_delete, calc_col_row_size, calc_freeze, calc_named_range, calc_sort, calc_autofilter, calc_validation,
         calc_conditional_format, calc_chart, calc_pivot, calc_find_replace, calc_protect, calc_recalculate, calc_hyperlink]
