"""Shared helpers for tool modules."""
import uno

from .. import bridge as b


def color(c):
    """Accept '#RRGGBB', 'RRGGBB', 0xRRGGBB int, or a basic name; return an int."""
    if isinstance(c, int):
        return c
    names = {"black": 0, "white": 0xFFFFFF, "red": 0xFF0000, "green": 0x008000, "blue": 0x0000FF, "yellow": 0xFFFF00,
             "orange": 0xFFA500, "purple": 0x800080, "gray": 0x808080, "grey": 0x808080, "cyan": 0x00FFFF, "magenta": 0xFF00FF}
    s = str(c).strip().lower()
    if s in names:
        return names[s]
    return int(s.lstrip("#"), 16)


def enum(type_name, value):
    return uno.Enum(type_name, value)


def struct(name, **fields):
    s = uno.createUnoStruct(name)
    for k, v in fields.items():
        setattr(s, k, v)
    return s


def apply_props(obj, props: dict):
    """setPropertyValue for each item; raise a readable error for unknown names."""
    for k, v in props.items():
        try:
            obj.setPropertyValue(k, v)
        except Exception as e:
            raise b.LOError(f"Cannot set '{k}': {e}")


def char_props(bold=None, italic=None, underline=None, strike=None, size=None, font=None, fg=None, bg=None, superscript=None, subscript=None, url=None):
    """Translate friendly formatting arguments into UNO character properties."""
    p = {}
    if bold is not None:
        p["CharWeight"] = 150.0 if bold else 100.0
    if italic is not None:
        p["CharPosture"] = enum("com.sun.star.awt.FontSlant", "ITALIC" if italic else "NONE")
    if underline is not None:
        p["CharUnderline"] = 1 if underline else 0
    if strike is not None:
        p["CharStrikeout"] = 1 if strike else 0
    if size is not None:
        p["CharHeight"] = float(size)
    if font:
        p["CharFontName"] = font
    if fg is not None:
        p["CharColor"] = color(fg)
    if bg is not None:
        p["CharBackColor"] = color(bg)
    if superscript:
        p["CharEscapement"], p["CharEscapementHeight"] = 33, 58
    if subscript:
        p["CharEscapement"], p["CharEscapementHeight"] = -33, 58
    if url is not None:
        p["HyperLinkURL"] = url
    return p


ALIGN = {"left": 0, "right": 1, "justify": 2, "center": 3}


def resolve_style(model, family, name):
    """Map a UI/display or differently-cased style name to the programmatic style name."""
    fam = model.getStyleFamilies().getByName(family)
    if fam.hasByName(name):
        return name
    low = name.lower().replace("_", " ")
    for n in fam.getElementNames():
        st = fam.getByName(n)
        if n.lower() == low or getattr(st, "DisplayName", "").lower() == low:
            return n
    raise b.LOError(f"No {family} style '{name}'. Use writer_list_styles to see the names.")
