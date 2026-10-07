"""Writer (text document) tools."""
import os

import uno

from .. import bridge as b
from ._util import ALIGN, apply_props, char_props, color, enum, resolve_style, struct

W = ("writer",)


def _text(doc_id):
    m = b.need(doc_id, *W)
    return m, m.getText()


def _paras(text):
    """Return paragraph objects at body level (tables are skipped)."""
    e, out = text.createEnumeration(), []
    while e.hasMoreElements():
        p = e.nextElement()
        if p.supportsService("com.sun.star.text.Paragraph"):
            out.append(p)
    return out


def _para(text, index):
    ps = _paras(text)
    if not -len(ps) <= index < len(ps):
        raise b.LOError(f"Paragraph index {index} out of range (0..{len(ps) - 1}).")
    return ps[index]


def _end(text):
    c = text.createTextCursor()
    c.gotoEnd(False)
    return c


def writer_get_text(doc_id: str, start: int = 0, count: int = 0) -> dict:
    """Return the document text. start/count select paragraphs (count=0 means all)."""
    _, t = _text(doc_id)
    ps = [p.getString() for p in _paras(t)]
    sel = ps[start:start + count] if count else ps[start:]
    return {"paragraph_count": len(ps), "text": "\n".join(sel)}


def writer_set_text(doc_id: str, text: str) -> dict:
    """Replace the entire body text. Use \\n for new paragraphs."""
    _, t = _text(doc_id)
    t.setString(text)
    return {"ok": True}


def writer_append(doc_id: str, text: str, style: str = "") -> dict:
    """Append text as new paragraph(s) at the end. Optional paragraph style (e.g. 'Heading 1', 'Text Body', 'Quotations')."""
    m, t = _text(doc_id)
    if style:
        style = resolve_style(m, "ParagraphStyles", style)
    for i, line in enumerate(text.split("\n")):
        c = _end(t)
        last = _paras(t)[-1]
        if last.getString() != "":
            t.insertControlCharacter(c, 0, False)  # PARAGRAPH_BREAK
            c = _end(t)
        c.setString(line)
        if style:
            c.setPropertyValue("ParaStyleName", style)
    return {"paragraphs": len(_paras(t))}


def writer_insert_paragraph(doc_id: str, text: str, index: int = -1, style: str = "") -> dict:
    """Insert a paragraph before paragraph `index` (-1 = at end)."""
    if index == -1:
        return writer_append(doc_id, text, style)
    m, t = _text(doc_id)
    p = _para(t, index)
    c = t.createTextCursorByRange(p.getStart())
    t.insertString(c, text, False)
    t.insertControlCharacter(c, 0, False)
    q = _para(t, index)
    if style:
        q.setPropertyValue("ParaStyleName", resolve_style(m, "ParagraphStyles", style))
    return {"ok": True}


def writer_delete_paragraph(doc_id: str, index: int) -> dict:
    """Delete paragraph `index` entirely."""
    m, t = _text(doc_id)
    p = _para(t, index)
    c = t.createTextCursorByRange(p)
    c.setString("")
    ps = _paras(t)
    if index < len(ps) and ps[index].getString() == "" and len(ps) > 1:
        cc = t.createTextCursorByRange(ps[index].getStart())
        cc.goRight(1, True)
        cc.setString("")
    return {"paragraphs": len(_paras(t))}


def writer_list_paragraphs(doc_id: str, start: int = 0, count: int = 50) -> list:
    """List paragraphs with index, style, alignment, and text."""
    _, t = _text(doc_id)
    out = []
    for i, p in enumerate(_paras(t)):
        if i < start or len(out) >= count:
            continue
        out.append({"index": i, "style": p.getPropertyValue("ParaStyleName"), "text": p.getString()})
    return out


def writer_outline(doc_id: str) -> list:
    """Headings (paragraphs with an outline level) in document order."""
    _, t = _text(doc_id)
    return [{"index": i, "level": p.getPropertyValue("OutlineLevel"), "text": p.getString()}
            for i, p in enumerate(_paras(t)) if p.getPropertyValue("OutlineLevel") > 0]


def writer_find_replace(doc_id: str, find: str, replace: str = None, regex: bool = False, match_case: bool = False, whole_words: bool = False) -> dict:
    """Find text (count + paragraph previews); when `replace` is given, replace all occurrences."""
    m, _ = _text(doc_id)
    d = m.createReplaceDescriptor() if replace is not None else m.createSearchDescriptor()
    d.setSearchString(find)
    d.SearchRegularExpression, d.SearchCaseSensitive, d.SearchWords = regex, match_case, whole_words
    if replace is not None:
        d.setReplaceString(replace)
        return {"replaced": m.replaceAll(d)}
    found = m.findAll(d)
    return {"count": found.getCount(), "matches": [found.getByIndex(i).getString() for i in range(min(found.getCount(), 50))]}


def writer_format_range(doc_id: str, paragraph: int = None, search: str = None, bold: bool = None, italic: bool = None,
                        underline: bool = None, strike: bool = None, size: float = None, font: str = None, color_fg: str = None,
                        color_bg: str = None, superscript: bool = None, subscript: bool = None, url: str = None,
                        align: str = None, style: str = None, spacing_above: int = None, spacing_below: int = None,
                        line_spacing_percent: int = None, indent_left: int = None, first_line_indent: int = None) -> dict:
    """Format a paragraph (by index) or every occurrence of `search` text. Character formatting applies to the selected text; align/style/spacing/indent (1/100 mm) apply to its paragraph(s)."""
    m, t = _text(doc_id)
    if paragraph is not None:
        targets = [_para(t, paragraph)]
    elif search:
        d = m.createSearchDescriptor()
        d.setSearchString(search)
        f = m.findAll(d)
        targets = [f.getByIndex(i) for i in range(f.getCount())]
        if not targets:
            raise b.LOError(f"Text not found: {search}")
    else:
        raise b.LOError("Provide paragraph= or search=.")
    cp = char_props(bold, italic, underline, strike, size, font, color_fg, color_bg, superscript, subscript, url)
    pp = {}
    if align:
        pp["ParaAdjust"] = ALIGN[align]
    if style:
        pp["ParaStyleName"] = resolve_style(m, "ParagraphStyles", style)
    if spacing_above is not None:
        pp["ParaTopMargin"] = spacing_above
    if spacing_below is not None:
        pp["ParaBottomMargin"] = spacing_below
    if line_spacing_percent:
        pp["ParaLineSpacing"] = struct("com.sun.star.style.LineSpacing", Mode=1, Height=line_spacing_percent)
    if indent_left is not None:
        pp["ParaLeftMargin"] = indent_left
    if first_line_indent is not None:
        pp["ParaFirstLineIndent"] = first_line_indent
    for r in targets:
        apply_props(r, cp)
        if pp:
            c = t.createTextCursorByRange(r.getStart())  # paragraph props go through a cursor in the paragraph
            apply_props(c, pp)
    return {"formatted": len(targets)}


def writer_list_styles(doc_id: str, family: str = "ParagraphStyles") -> list:
    """List style names. family: ParagraphStyles | CharacterStyles | PageStyles | FrameStyles | NumberingStyles."""
    m = b.need(doc_id, *W)
    return list(m.getStyleFamilies().getByName(family).getElementNames())


def writer_apply_style(doc_id: str, style: str, paragraph: int, family: str = "ParaStyleName") -> dict:
    """Apply a paragraph style (or CharStyleName via family) to a paragraph."""
    m, t = _text(doc_id)
    fam = "ParagraphStyles" if family == "ParaStyleName" else "CharacterStyles"
    _para(t, paragraph).setPropertyValue(family, resolve_style(m, fam, style))
    return {"ok": True}


def writer_create_style(doc_id: str, name: str, family: str = "ParagraphStyles", parent: str = "", properties: dict = None) -> dict:
    """Create (or update) a style and set UNO properties, e.g. {'CharHeight': 14, 'CharColor': 255, 'ParaAdjust': 3}."""
    m = b.need(doc_id, *W)
    fam = m.getStyleFamilies().getByName(family)
    if fam.hasByName(name):
        s = fam.getByName(name)
    else:
        s = m.createInstance("com.sun.star.style." + family[:-1])
        fam.insertByName(name, s)
    if parent:
        s.setParentStyle(parent)
    apply_props(s, {k: color(v) if "Color" in k and isinstance(v, str) else v for k, v in (properties or {}).items()})
    return {"style": name}


def writer_insert_table(doc_id: str, rows: int = 0, cols: int = 0, data: list = None, name: str = "", header: bool = True, style_autoformat: str = "") -> dict:
    """Insert a table at the end. Pass `data` (list of rows) or rows/cols. Numbers stay numeric; strings starting with '=' become formulas."""
    m, t = _text(doc_id)
    if data:
        rows, cols = len(data), max(len(r) for r in data)
    if rows < 1 or cols < 1:
        raise b.LOError("Give data or rows and cols.")
    tbl = m.createInstance("com.sun.star.text.TextTable")
    tbl.initialize(rows, cols)
    if name:
        tbl.setName(name)
    t.insertTextContent(_end(t), tbl, False)
    for r, row in enumerate(data or []):
        for c, v in enumerate(row):
            cell = tbl.getCellByPosition(c, r)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cell.setValue(v)
            elif isinstance(v, str) and v.startswith("="):
                cell.setFormula(v[1:])
            else:
                cell.setString("" if v is None else str(v))
    tbl.setPropertyValue("RepeatHeadline", header)
    tbl.setPropertyValue("HeaderRowCount", 1 if header else 0)
    if style_autoformat:
        tbl.autoFormat(style_autoformat) if hasattr(tbl, "autoFormat") else None
    return {"table": tbl.getName(), "rows": rows, "cols": cols}


def writer_list_tables(doc_id: str) -> list:
    """List tables with sizes."""
    m = b.need(doc_id, *W)
    ts = m.getTextTables()
    return [{"name": n, "rows": ts.getByName(n).getRows().getCount(), "cols": ts.getByName(n).getColumns().getCount()} for n in ts.getElementNames()]


def writer_get_table(doc_id: str, table: str) -> dict:
    """Read a table as a 2D list of cell values."""
    tbl = b.need(doc_id, *W).getTextTables().getByName(table)
    return {"data": [list(r) for r in tbl.getDataArray()]}


def writer_set_table_cell(doc_id: str, table: str, cell: str, value: object, bg: str = None, bold: bool = None) -> dict:
    """Set a cell by name ('A1'). Numbers stay numeric, '=SUM(A1:A3)' is a formula."""
    c = b.need(doc_id, *W).getTextTables().getByName(table).getCellByName(cell)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        c.setValue(value)
    elif isinstance(value, str) and value.startswith("="):
        c.setFormula(value[1:])
    else:
        c.setString(str(value))
    if bg is not None:
        c.setPropertyValue("BackColor", color(bg))
    if bold is not None:
        c.setPropertyValue("CharWeight", 150.0 if bold else 100.0)
    return {"ok": True}


def writer_table_edit(doc_id: str, table: str, action: str, index: int = 0, count: int = 1) -> dict:
    """Edit table structure. action: insert_rows | insert_cols | delete_rows | delete_cols (index is 0-based)."""
    tbl = b.need(doc_id, *W).getTextTables().getByName(table)
    rc = tbl.getRows() if action.endswith("rows") else tbl.getColumns()
    (rc.insertByIndex if action.startswith("insert") else rc.removeByIndex)(index, count)
    return {"rows": tbl.getRows().getCount(), "cols": tbl.getColumns().getCount()}


def writer_insert_list(doc_id: str, items: list, ordered: bool = False) -> dict:
    """Append a bulleted (default) or numbered list."""
    _, t = _text(doc_id)
    for it in items:
        writer_append(doc_id, str(it), "")
        _paras(t)[-1].setPropertyValue("NumberingStyleName", "Numbering 123" if ordered else "List 1")
    return {"items": len(items)}


def writer_insert_image(doc_id: str, path: str, width_mm: float = 0, height_mm: float = 0, as_char: bool = True, paragraph: int = -1) -> dict:
    """Insert an image file at the end (or at the start of `paragraph`). Width/height in mm (0 = natural size / keep aspect)."""
    if not os.path.exists(os.path.expanduser(path)):
        raise b.LOError(f"Image not found: {path}")
    m, t = _text(doc_id)
    g = m.createInstance("com.sun.star.text.TextGraphicObject")
    g.setPropertyValue("GraphicURL", b.to_url(path))
    g.setPropertyValue("AnchorType", enum("com.sun.star.text.TextContentAnchorType", "AS_CHARACTER" if as_char else "AT_PARAGRAPH"))
    cur = _end(t) if paragraph == -1 else t.createTextCursorByRange(_para(t, paragraph).getStart())
    t.insertTextContent(cur, g, False)
    nat = g.getPropertyValue("ActualSize")
    w, h = int(width_mm * 100), int(height_mm * 100)
    if w and not h:
        h = int(nat.Height * w / max(nat.Width, 1))
    if h and not w:
        w = int(nat.Width * h / max(nat.Height, 1))
    if w and h:
        g.setPropertyValue("Width", w)
        g.setPropertyValue("Height", h)
    return {"name": g.getName()}


def writer_page_setup(doc_id: str, style: str = "", width_mm: float = None, height_mm: float = None, landscape: bool = None,
                      margin_top_mm: float = None, margin_bottom_mm: float = None, margin_left_mm: float = None,
                      margin_right_mm: float = None, columns: int = None) -> dict:
    """Read/modify a page style (default: the current page's style). Returns the resulting size and margins in mm."""
    m = b.need(doc_id, *W)
    name = style or m.getCurrentController().getViewCursor().getPropertyValue("PageStyleName")
    ps = m.getStyleFamilies().getByName("PageStyles").getByName(name)
    w, h = ps.getPropertyValue("Width"), ps.getPropertyValue("Height")
    if width_mm is not None or height_mm is not None:
        w, h = int((width_mm or w / 100) * 100), int((height_mm or h / 100) * 100)
    if landscape is not None and (landscape != (w > h)):
        w, h = h, w
    ps.setPropertyValue("IsLandscape", w > h)
    ps.setPropertyValue("Width", w)
    ps.setPropertyValue("Height", h)
    for key, val in (("TopMargin", margin_top_mm), ("BottomMargin", margin_bottom_mm), ("LeftMargin", margin_left_mm), ("RightMargin", margin_right_mm)):
        if val is not None:
            ps.setPropertyValue(key, int(val * 100))
    if columns:
        tc = ps.getPropertyValue("TextColumns")
        tc.setColumnCount(columns)
        ps.setPropertyValue("TextColumns", tc)
    return {"style": name, "width_mm": ps.Width / 100, "height_mm": ps.Height / 100,
            "margins_mm": {k: ps.getPropertyValue(k + "Margin") / 100 for k in ("Top", "Bottom", "Left", "Right")}}


def writer_header_footer(doc_id: str, header: str = None, footer: str = None, page_numbers: str = "", style: str = "") -> dict:
    """Set header/footer text ('' removes it). page_numbers: '' | 'header' | 'footer' appends 'Page N' to that area (right after any text)."""
    m = b.need(doc_id, *W)
    name = style or m.getCurrentController().getViewCursor().getPropertyValue("PageStyleName")
    ps = m.getStyleFamilies().getByName("PageStyles").getByName(name)
    for kind, val in (("Header", header), ("Footer", footer)):
        if val is not None:
            ps.setPropertyValue(f"{kind}IsOn", True)  # the text object is only reliable while the area is on
            ps.getPropertyValue(f"{kind}Text").setString(val)  # '' really clears old content
            ps.setPropertyValue(f"{kind}IsOn", val != "" or page_numbers == kind.lower())
    if page_numbers in ("header", "footer"):
        kind = page_numbers.capitalize()
        ps.setPropertyValue(f"{kind}IsOn", True)
        txt = ps.getPropertyValue(f"{kind}Text")
        c = txt.createTextCursor()
        c.gotoEnd(False)
        txt.insertString(c, ("  " if txt.getString() else "") + "Page ", False)
        f = m.createInstance("com.sun.star.text.TextField.PageNumber")
        f.setPropertyValue("NumberingType", 4)
        txt.insertTextContent(c, f, False)
    return {"style": name}


def writer_page_break(doc_id: str) -> dict:
    """Insert a page break after the last paragraph."""
    _, t = _text(doc_id)
    writer_append(doc_id, "", "")
    last = _paras(t)[-1]
    last.setPropertyValue("BreakType", enum("com.sun.star.style.BreakType", "PAGE_BEFORE"))
    return {"ok": True}


def writer_toc(doc_id: str, title: str = "Table of Contents", levels: int = 3, paragraph: int = 0) -> dict:
    """Insert a table of contents before `paragraph` (default top) and update it."""
    m, t = _text(doc_id)
    idx = m.createInstance("com.sun.star.text.ContentIndex")
    idx.setPropertyValue("Title", title)
    idx.setPropertyValue("Level", levels)
    idx.setPropertyValue("CreateFromOutline", True)
    t.insertTextContent(t.createTextCursorByRange(_para(t, paragraph).getStart()), idx, False)
    idx.update()
    return {"ok": True}


def writer_update_indexes(doc_id: str) -> dict:
    """Refresh all indexes/TOCs and fields."""
    m = b.need(doc_id, *W)
    idxs = m.getDocumentIndexes()
    for i in range(idxs.getCount()):
        idxs.getByIndex(i).update()
    m.getTextFields().refresh()
    return {"indexes": idxs.getCount()}


def writer_bookmark(doc_id: str, action: str, name: str = "", search: str = "") -> object:
    """action: add (bookmark the first occurrence of `search`, or end of doc) | list | goto | delete."""
    m, t = _text(doc_id)
    bms = m.getBookmarks()
    if action == "list":
        return list(bms.getElementNames())
    if action == "add":
        if search:
            d = m.createSearchDescriptor()
            d.setSearchString(search)
            r = m.findFirst(d)
            if r is None:
                raise b.LOError(f"Text not found: {search}")
            cur = t.createTextCursorByRange(r)
        else:
            cur = _end(t)
        bm = m.createInstance("com.sun.star.text.Bookmark")
        bm.setName(name)
        t.insertTextContent(cur, bm, True)
        return {"bookmark": name}
    bm = bms.getByName(name)
    if action == "delete":
        t.removeTextContent(bm)
        return {"deleted": name}
    if action == "goto":
        m.getCurrentController().getViewCursor().gotoRange(bm.getAnchor(), False)
        return {"ok": True}
    raise b.LOError("action must be add|list|goto|delete")


def writer_comment(doc_id: str, text: str, search: str = "", author: str = "Claude") -> dict:
    """Attach a comment (annotation) to the first occurrence of `search`, or the end of the document."""
    m, t = _text(doc_id)
    cur = _end(t)
    if search:
        d = m.createSearchDescriptor()
        d.setSearchString(search)
        r = m.findFirst(d)
        if r is None:
            raise b.LOError(f"Text not found: {search}")
        cur = t.createTextCursorByRange(r)
    a = m.createInstance("com.sun.star.text.TextField.Annotation")
    a.setPropertyValue("Content", text)
    a.setPropertyValue("Author", author)
    t.insertTextContent(cur, a, False)
    return {"ok": True}


def writer_list_comments(doc_id: str) -> list:
    """List comments (author, content)."""
    m = b.need(doc_id, *W)
    e, out = m.getTextFields().createEnumeration(), []
    while e.hasMoreElements():
        f = e.nextElement()
        if f.supportsService("com.sun.star.text.TextField.Annotation"):
            out.append({"author": f.Author, "content": f.Content, "anchor": f.getAnchor().getString()})
    return out


def writer_footnote(doc_id: str, text: str, search: str = "", endnote: bool = False) -> dict:
    """Add a footnote/endnote at the first occurrence of `search` (or document end)."""
    m, t = _text(doc_id)
    cur = _end(t)
    if search:
        d = m.createSearchDescriptor()
        d.setSearchString(search)
        r = m.findFirst(d)
        if r is None:
            raise b.LOError(f"Text not found: {search}")
        cur = t.createTextCursorByRange(r.getEnd())
    fn = m.createInstance("com.sun.star.text.Endnote" if endnote else "com.sun.star.text.Footnote")
    t.insertTextContent(cur, fn, False)
    fn.setString(text)
    return {"ok": True}


def writer_track_changes(doc_id: str, action: str) -> object:
    """action: on | off | list | accept_all | reject_all."""
    m = b.need(doc_id, *W)
    if action in ("on", "off"):
        m.setPropertyValue("RecordChanges", action == "on")
        return {"recording": action == "on"}
    if action == "list":
        r = m.getRedlines().createEnumeration()
        out = []
        while r.hasMoreElements():
            x = r.nextElement()
            out.append({"type": x.getPropertyValue("RedlineType"), "author": x.getPropertyValue("RedlineAuthor")})
        return out
    cmd = {"accept_all": ".uno:AcceptAllTrackedChanges", "reject_all": ".uno:RejectAllTrackedChanges"}[action]
    uno_dispatch(m, cmd)
    return {"ok": True}


def uno_dispatch(m, cmd):
    helper = b.create("com.sun.star.frame.DispatchHelper")
    helper.executeDispatch(m.getCurrentController().getFrame(), cmd, "", 0, ())


def writer_insert_field(doc_id: str, kind: str = "date") -> dict:
    """Insert a field at the end. kind: date | time | page | page_count | author | title | file_name."""
    m, t = _text(doc_id)
    svc = {"date": "DateTime", "time": "DateTime", "page": "PageNumber", "page_count": "PageCount", "author": "Author",
           "title": "DocInformation.Title", "file_name": "FileName"}[kind]
    f = m.createInstance("com.sun.star.text.TextField." + svc)
    if svc == "DateTime":
        f.setPropertyValue("IsDate", kind == "date")
        f.setPropertyValue("IsFixed", False)
    t.insertTextContent(_end(t), f, False)
    return {"ok": True}


def writer_text_stats(doc_id: str) -> dict:
    """Character, word and paragraph counts."""
    m = b.need(doc_id, *W)
    return {n: m.getPropertyValue(n) for n in ("CharacterCount", "WordCount", "ParagraphCount")}


TOOLS = [writer_get_text, writer_set_text, writer_append, writer_insert_paragraph, writer_delete_paragraph, writer_list_paragraphs,
         writer_outline, writer_find_replace, writer_format_range, writer_list_styles, writer_apply_style, writer_create_style,
         writer_insert_table, writer_list_tables, writer_get_table, writer_set_table_cell, writer_table_edit, writer_insert_list,
         writer_insert_image, writer_page_setup, writer_header_footer, writer_page_break, writer_toc, writer_update_indexes,
         writer_bookmark, writer_comment, writer_list_comments, writer_footnote, writer_track_changes, writer_insert_field, writer_text_stats]
