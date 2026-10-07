"""Impress and Draw tools. A 'slide' is a draw page; Draw documents use the same tools."""
import os

import uno

from .. import bridge as b
from ._util import ALIGN, color, enum, struct

K = ("impress", "draw")
LAYOUTS = {"title": 0, "title_content": 1, "title_2content": 3, "title_only": 19, "blank": 20}


def _page(doc_id, slide):
    m = b.need(doc_id, *K)
    pages = m.getDrawPages()
    if not 0 <= slide < pages.getCount():
        raise b.LOError(f"Slide {slide} out of range (0..{pages.getCount() - 1}).")
    return m, pages.getByIndex(slide)


def _mm(v):
    return int(v * 100)


def _shape_info(i, s):
    t = s.getShapeType().split(".")[-1]
    info = {"index": i, "type": t, "x_mm": s.Position.X / 100, "y_mm": s.Position.Y / 100,
            "w_mm": s.Size.Width / 100, "h_mm": s.Size.Height / 100}
    try:
        info["text"] = s.getString()
    except Exception:
        pass
    try:
        info["name"] = s.getName()
    except Exception:
        pass
    return info


def impress_list_slides(doc_id: str) -> list:
    """List slides with layout, title text, shape count and slide size."""
    m = b.need(doc_id, *K)
    out = []
    for i in range(m.getDrawPages().getCount()):
        p = m.getDrawPages().getByIndex(i)
        title = ""
        for j in range(p.getCount()):
            s = p.getByIndex(j)
            if "TitleTextShape" in s.getShapeType():
                title = s.getString()
        out.append({"index": i, "name": p.Name, "title": title, "shapes": p.getCount(), "width_mm": p.Width / 100, "height_mm": p.Height / 100})
    return out


def impress_add_slide(doc_id: str, layout: str = "title_content", title: str = "", body: str = "", index: int = -1) -> dict:
    """Add a slide (layout: title | title_content | title_2content | title_only | blank) and fill the title/body placeholders. Body lines separated by \\n."""
    m = b.need(doc_id, *K)
    pages = m.getDrawPages()
    pos = pages.getCount() if index < 0 else index
    if pages.getCount() == 1 and pos == 1 and pages.getByIndex(0).getCount() == 0 and False:
        pass
    p = pages.insertNewByIndex(pos - 1 if pos > 0 else 0) if pos > 0 else pages.insertNewByIndex(0)
    new = pages.getByIndex(pos)
    if m.supportsService("com.sun.star.presentation.PresentationDocument"):
        new.setPropertyValue("Layout", LAYOUTS[layout])
    impress_fill(doc_id, pos, title, body)
    return {"slide": pos}


def impress_fill(doc_id: str, slide: int, title: str = "", body: str = "") -> dict:
    """Fill the title and body placeholders of a slide."""
    _, p = _page(doc_id, slide)
    outl = 0
    for j in range(p.getCount()):
        s = p.getByIndex(j)
        t = s.getShapeType()
        if "TitleTextShape" in t and title:
            s.setString(title)
        elif ("OutlinerShape" in t or "SubtitleShape" in t) and body:
            outl += 1
            if outl == 1:
                s.setString(body)
    return {"ok": True}


def impress_delete_slide(doc_id: str, slide: int) -> dict:
    """Delete a slide."""
    m, p = _page(doc_id, slide)
    m.getDrawPages().remove(p)
    return {"slides": m.getDrawPages().getCount()}


def impress_duplicate_slide(doc_id: str, slide: int) -> dict:
    """Duplicate a slide (the copy is placed right after it)."""
    m, p = _page(doc_id, slide)
    m.duplicate(p)
    return {"slides": m.getDrawPages().getCount()}


def impress_move_slide(doc_id: str, slide: int, to: int) -> dict:
    """Move a slide to a new position."""
    m, p = _page(doc_id, slide)
    c = m.getCurrentController()
    c.setCurrentPage(p)
    helper = b.create("com.sun.star.frame.DispatchHelper")
    cmd = ".uno:MovePageUp" if to < slide else ".uno:MovePageDown"
    for _ in range(abs(to - slide)):
        helper.executeDispatch(c.getFrame(), cmd, "", 0, ())
    return {"ok": True}


def impress_set_layout(doc_id: str, slide: int, layout: str) -> dict:
    """Change a slide's layout."""
    _, p = _page(doc_id, slide)
    p.setPropertyValue("Layout", LAYOUTS[layout])
    return {"ok": True}


def impress_list_shapes(doc_id: str, slide: int) -> list:
    """List the shapes on a slide with index, type, position/size (mm) and text."""
    _, p = _page(doc_id, slide)
    return [_shape_info(i, p.getByIndex(i)) for i in range(p.getCount())]


_SHAPES = {"rectangle": "RectangleShape", "ellipse": "EllipseShape", "line": "LineShape", "text": "TextShape", "connector": "ConnectorShape"}
_CUSTOM = {"triangle": "isosceles-triangle", "diamond": "diamond", "star": "star5", "right_arrow": "right-arrow", "rounded_rectangle": "round-rectangle",
           "pentagon": "pentagon", "hexagon": "hexagon", "heart": "heart", "cloud": "cloud", "callout": "round-rectangular-callout"}


def _style(s, fill, line_color, line_width_mm, text, size, bold, fg, align, font):
    if fill:
        s.setPropertyValue("FillStyle", enum("com.sun.star.drawing.FillStyle", "SOLID"))
        s.setPropertyValue("FillColor", color(fill))
    elif fill == "":
        s.setPropertyValue("FillStyle", enum("com.sun.star.drawing.FillStyle", "NONE"))
    if line_color:
        s.setPropertyValue("LineColor", color(line_color))
    if line_width_mm is not None:
        s.setPropertyValue("LineWidth", _mm(line_width_mm))
    if text:
        s.setString(text)
    if size: s.setPropertyValue("CharHeight", float(size))
    if bold is not None: s.setPropertyValue("CharWeight", 150.0 if bold else 100.0)
    if fg: s.setPropertyValue("CharColor", color(fg))
    if font: s.setPropertyValue("CharFontName", font)
    if align: s.setPropertyValue("ParaAdjust", ALIGN[align])


def impress_add_shape(doc_id: str, slide: int, kind: str, x_mm: float = 20, y_mm: float = 20, w_mm: float = 60, h_mm: float = 30,
                      fill: str = None, line_color: str = None, line_width_mm: float = None, text: str = "", size: float = None,
                      bold: bool = None, text_color: str = None, align: str = None, font: str = None, name: str = "") -> dict:
    """Add a shape. kind: rectangle | ellipse | line | text | triangle | diamond | star | right_arrow | rounded_rectangle | pentagon | hexagon | heart | cloud | callout. For 'line', (x,y)->(x+w,y+h). fill '' = no fill."""
    m, p = _page(doc_id, slide)
    if kind in _CUSTOM:
        s = m.createInstance("com.sun.star.drawing.CustomShape")
    elif kind in _SHAPES:
        s = m.createInstance("com.sun.star.drawing." + _SHAPES[kind])
    else:
        raise b.LOError(f"Unknown kind. Use one of {sorted(list(_SHAPES) + list(_CUSTOM))}")
    p.add(s)
    s.setPosition(struct("com.sun.star.awt.Point", X=_mm(x_mm), Y=_mm(y_mm)))
    s.setSize(struct("com.sun.star.awt.Size", Width=_mm(w_mm), Height=_mm(h_mm)))
    if kind in _CUSTOM:
        s.setPropertyValue("CustomShapeGeometry", b.props(Type=_CUSTOM[kind]))
    _style(s, fill, line_color, line_width_mm, text, size, bold, text_color, align, font)
    if name:
        s.setName(name)
    return {"index": p.getCount() - 1}


def impress_add_text(doc_id: str, slide: int, text: str, x_mm: float = 20, y_mm: float = 20, w_mm: float = 100, h_mm: float = 20,
                     size: float = 18, bold: bool = None, color_fg: str = None, align: str = None, font: str = None) -> dict:
    """Add a text box."""
    return impress_add_shape(doc_id, slide, "text", x_mm, y_mm, w_mm, h_mm, None, None, None, text, size, bold, color_fg, align, font)


def impress_add_image(doc_id: str, slide: int, path: str, x_mm: float = 20, y_mm: float = 20, w_mm: float = 0, h_mm: float = 0) -> dict:
    """Add an image (aspect ratio is kept when only one of w/h is given; natural size otherwise)."""
    if not os.path.exists(os.path.expanduser(path)):
        raise b.LOError(f"Image not found: {path}")
    m, p = _page(doc_id, slide)
    url = b.to_url(path)
    d = b.create("com.sun.star.graphic.GraphicProvider").queryGraphicDescriptor(b.props(URL=url))
    nat = d.getPropertyValue("Size100thMM")
    w, h = _mm(w_mm), _mm(h_mm)
    if w and not h: h = int(nat.Height * w / max(nat.Width, 1))
    elif h and not w: w = int(nat.Width * h / max(nat.Height, 1))
    elif not (w or h): w, h = nat.Width, nat.Height
    s = m.createInstance("com.sun.star.drawing.GraphicObjectShape")
    p.add(s)
    s.setPropertyValue("GraphicURL", url)
    s.setPosition(struct("com.sun.star.awt.Point", X=_mm(x_mm), Y=_mm(y_mm)))
    s.setSize(struct("com.sun.star.awt.Size", Width=w, Height=h))
    return {"index": p.getCount() - 1}


def impress_add_table(doc_id: str, slide: int, data: list, x_mm: float = 20, y_mm: float = 40, w_mm: float = 160, h_mm: float = 60) -> dict:
    """Add a table from a 2D list."""
    m, p = _page(doc_id, slide)
    rows, cols = len(data), max(len(r) for r in data)
    s = m.createInstance("com.sun.star.drawing.TableShape")
    p.add(s)
    s.setPosition(struct("com.sun.star.awt.Point", X=_mm(x_mm), Y=_mm(y_mm)))
    s.setSize(struct("com.sun.star.awt.Size", Width=_mm(w_mm), Height=_mm(h_mm)))
    model = s.getPropertyValue("Model")
    if model.ColumnCount < cols:
        model.getColumns().insertByIndex(model.ColumnCount, cols - model.ColumnCount)
    if model.RowCount < rows:
        model.getRows().insertByIndex(model.RowCount, rows - model.RowCount)
    for r, row in enumerate(data):
        for c, v in enumerate(row):
            model.getCellByPosition(c, r).setString("" if v is None else str(v))
    return {"index": p.getCount() - 1}


def impress_edit_shape(doc_id: str, slide: int, index: int, text: str = None, x_mm: float = None, y_mm: float = None, w_mm: float = None,
                       h_mm: float = None, fill: str = None, line_color: str = None, size: float = None, bold: bool = None,
                       text_color: str = None, rotation_deg: float = None, properties: dict = None) -> dict:
    """Edit a shape. `properties` is any raw UNO property map for things not covered."""
    _, p = _page(doc_id, slide)
    s = p.getByIndex(index)
    if x_mm is not None or y_mm is not None:
        s.setPosition(struct("com.sun.star.awt.Point", X=_mm(x_mm) if x_mm is not None else s.Position.X, Y=_mm(y_mm) if y_mm is not None else s.Position.Y))
    if w_mm is not None or h_mm is not None:
        s.setSize(struct("com.sun.star.awt.Size", Width=_mm(w_mm) if w_mm is not None else s.Size.Width, Height=_mm(h_mm) if h_mm is not None else s.Size.Height))
    _style(s, fill, line_color, None, text, size, bold, text_color, None, None)
    if rotation_deg is not None:
        s.setPropertyValue("RotateAngle", int(rotation_deg * 100))
    for k, v in (properties or {}).items():
        s.setPropertyValue(k, v)
    return _shape_info(index, s)


def impress_delete_shape(doc_id: str, slide: int, index: int) -> dict:
    """Delete a shape by index."""
    _, p = _page(doc_id, slide)
    p.remove(p.getByIndex(index))
    return {"shapes": p.getCount()}


def impress_arrange(doc_id: str, slide: int, index: int, action: str) -> dict:
    """action: front | back | forward | backward (z-order)."""
    _, p = _page(doc_id, slide)
    s = p.getByIndex(index)
    z = s.getPropertyValue("ZOrder")
    s.setPropertyValue("ZOrder", {"front": p.getCount() - 1, "back": 0, "forward": z + 1, "backward": max(z - 1, 0)}[action])
    return {"ok": True}


def impress_notes(doc_id: str, slide: int, text: str = None) -> dict:
    """Read or set speaker notes."""
    _, p = _page(doc_id, slide)
    np = p.getNotesPage()
    for j in range(np.getCount()):
        s = np.getByIndex(j)
        if "NotesShape" in s.getShapeType():
            if text is not None:
                s.setString(text)
            return {"notes": s.getString()}
    return {"notes": ""}


def impress_transition(doc_id: str, slide: int, effect: str = "FADE_FROM_LEFT", speed: str = "MEDIUM", auto_advance_s: float = None) -> dict:
    """Slide transition. effect: NONE | FADE_FROM_LEFT | FADE_FROM_RIGHT | FADE_FROM_TOP | FADE_FROM_BOTTOM | DISSOLVE | FADE_TO_CENTER | WAVYLINE_FROM_LEFT | ... (FadeEffect names). speed: SLOW | MEDIUM | FAST."""
    _, p = _page(doc_id, slide)
    p.setPropertyValue("Effect", enum("com.sun.star.presentation.FadeEffect", effect.upper()))
    p.setPropertyValue("Speed", enum("com.sun.star.presentation.AnimationSpeed", speed.upper()))
    if auto_advance_s is not None:
        p.setPropertyValue("Change", 1)
        p.setPropertyValue("Duration", int(auto_advance_s))
    return {"ok": True}


def impress_background(doc_id: str, slide: int, fill: str) -> dict:
    """Set a solid background colour for a slide."""
    m, p = _page(doc_id, slide)
    bg = m.createInstance("com.sun.star.drawing.Background")
    bg.setPropertyValue("FillStyle", enum("com.sun.star.drawing.FillStyle", "SOLID"))
    bg.setPropertyValue("FillColor", color(fill))
    p.setPropertyValue("Background", bg)
    return {"ok": True}


def impress_master(doc_id: str) -> list:
    """List master slides and their placeholder shapes (edit them with uno tools for theme-wide changes)."""
    m = b.need(doc_id, *K)
    ms = m.getMasterPages()
    return [{"index": i, "name": ms.getByIndex(i).Name, "shapes": [_shape_info(j, ms.getByIndex(i).getByIndex(j)) for j in range(ms.getByIndex(i).getCount())]} for i in range(ms.getCount())]


def impress_export_slide(doc_id: str, slide: int, path: str, format: str = "png") -> dict:
    """Export one slide as png/jpg/svg/pdf/gif."""
    _, p = _page(doc_id, slide)
    f = b.create("com.sun.star.drawing.GraphicExportFilter")
    f.setSourceDocument(p)
    mime = {"png": "image/png", "jpg": "image/jpeg", "svg": "image/svg+xml", "gif": "image/gif", "pdf": "application/pdf"}[format]
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(path))), exist_ok=True)
    f.filter(b.props(URL=b.to_url(path), MediaType=mime))
    return {"saved": b.to_url(path)}


def impress_start_show(doc_id: str) -> dict:
    """Start the slideshow (needs a visible window; headless servers may refuse)."""
    b.need(doc_id, "impress").getPresentation().start()
    return {"ok": True}


TOOLS = [impress_list_slides, impress_add_slide, impress_fill, impress_delete_slide, impress_duplicate_slide, impress_move_slide,
         impress_set_layout, impress_list_shapes, impress_add_shape, impress_add_text, impress_add_image, impress_add_table,
         impress_edit_shape, impress_delete_shape, impress_arrange, impress_notes, impress_transition, impress_background,
         impress_master, impress_export_slide, impress_start_show]
