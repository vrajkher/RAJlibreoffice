"""Generic UNO access: reach every API LibreOffice exposes, even without a dedicated tool."""
import contextlib
import io
import traceback

import uno

from .. import bridge as b


def _to_uno(v):
    """Decode JSON args: {"handle":..}, {"struct":..,"fields":..}, {"enum":..}, {"props":{..}}, {"any":..}."""
    if isinstance(v, dict):
        if "handle" in v:
            return b.handle(v["handle"])
        if "enum" in v:
            t, _, name = v["enum"].rpartition(".")
            return uno.Enum(t, name)
        if "struct" in v:
            s = uno.createUnoStruct(v["struct"])
            for k, x in v.get("fields", {}).items():
                setattr(s, k, _to_uno(x))
            return s
        if "props" in v:
            return b.props(**{k: _to_uno(x) for k, x in v["props"].items()})
        if "const" in v:
            return uno.getConstantByName(v["const"])
        return {k: _to_uno(x) for k, x in v.items()}
    if isinstance(v, list):
        return tuple(_to_uno(x) for x in v)
    return v


def _from_uno(v, depth=0):
    """Encode a UNO return value into JSON-friendly data, registering handles for objects."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (tuple, list)):
        return [_from_uno(x, depth + 1) for x in v][:500]
    if isinstance(v, uno.Enum):
        return {"enum": f"{v.typeName}.{v.value}"}
    if isinstance(v, uno.Type):
        return {"type": v.typeName}
    if hasattr(v, "__dict__") and type(v).__module__ == "uno" or type(v).__name__ == "pyuno":
        return {"handle": b.new_handle(v), "services": _services(v)}
    if hasattr(v, "value") and hasattr(v, "typeName"):
        return str(v)
    try:  # UNO struct
        d = {k: _from_uno(getattr(v, k), depth + 1) for k in dir(v) if not k.startswith("_") and not callable(getattr(v, k))}
        return d if d else str(v)
    except Exception:
        return str(v)


def _services(o):
    try:
        return list(o.getSupportedServiceNames())[:6]
    except Exception:
        return []


def uno_root(doc_id: str, part: str = "model") -> dict:
    """Get a handle for the document's root objects. part: model | controller | frame | desktop | text | sheets | draw_pages | styles | doc_settings."""
    m = b.doc(doc_id) if doc_id else None
    obj = {"model": lambda: m, "controller": lambda: m.getCurrentController(), "frame": lambda: m.getCurrentController().getFrame(),
           "desktop": lambda: b.desktop(), "text": lambda: m.getText(), "sheets": lambda: m.getSheets(),
           "draw_pages": lambda: m.getDrawPages(), "styles": lambda: m.getStyleFamilies(),
           "doc_settings": lambda: m.createInstance("com.sun.star.document.Settings")}[part]()
    return _from_uno(obj)


def uno_create(service: str, doc_id: str = "") -> dict:
    """Instantiate a service. With doc_id, the document factory is used (e.g. com.sun.star.text.TextTable, com.sun.star.drawing.RectangleShape); otherwise the global service manager."""
    obj = b.doc(doc_id).createInstance(service) if doc_id else b.create(service)
    return _from_uno(obj)


def uno_call(handle: str, method: str, args: list = None) -> object:
    """Call any UNO method on a handle (or doc_id). Args are JSON; see uno_help for special encodings. Returns the result; UNO objects come back as handles."""
    o = b.handle(handle)
    return _from_uno(getattr(o, method)(*[_to_uno(a) for a in (args or [])]))


def uno_get(handle: str, property: str) -> object:
    """Read a property (via getPropertyValue, falling back to an attribute)."""
    o = b.handle(handle)
    try:
        return _from_uno(o.getPropertyValue(property))
    except Exception:
        return _from_uno(getattr(o, property))


def uno_set(handle: str, property: str, value: object) -> dict:
    """Set a property."""
    o = b.handle(handle)
    v = _to_uno(value)
    try:
        o.setPropertyValue(property, v)
    except Exception:
        setattr(o, property, v)
    return {"ok": True}


def uno_set_many(handle: str, properties: dict) -> dict:
    """Set several properties at once."""
    for k, v in properties.items():
        uno_set(handle, k, v)
    return {"ok": True, "count": len(properties)}


def uno_inspect(handle: str) -> dict:
    """Describe an object: services, properties (name/type) and methods, so you can discover the API."""
    o = b.handle(handle)
    out = {"services": _services(o), "properties": [], "methods": []}
    try:
        out["properties"] = [{"name": p.Name, "type": p.Type.typeName} for p in o.getPropertySetInfo().getProperties()]
    except Exception:
        pass
    try:
        out["methods"] = sorted(m for m in dir(o) if not m.startswith("_") and callable(getattr(o, m, None)))
    except Exception:
        pass
    return out


def uno_enumerate(handle: str) -> list:
    """List the children of a container: by name (XNameAccess), index (XIndexAccess) or enumeration (XEnumerationAccess)."""
    o = b.handle(handle)
    if hasattr(o, "getElementNames"):
        return [{"name": n, "value": _from_uno(o.getByName(n))} for n in o.getElementNames()]
    if hasattr(o, "createEnumeration"):
        e, out = o.createEnumeration(), []
        while e.hasMoreElements():
            out.append(_from_uno(e.nextElement()))
        return out
    if hasattr(o, "getCount"):
        return [_from_uno(o.getByIndex(i)) for i in range(o.getCount())]
    raise b.LOError("Object is not a container.")


def release_handle(handle: str) -> dict:
    """Free a handle."""
    b._handles.pop(handle, None)
    return {"ok": True}


def dispatch_command(doc_id: str, command: str, arguments: dict = None) -> dict:
    """Run any LibreOffice UI command, e.g. '.uno:Bold', '.uno:SelectAll', '.uno:UpdateAllIndexes'. Arguments is a name->value map."""
    m = b.doc(doc_id)
    frame = m.getCurrentController().getFrame()
    helper = b.create("com.sun.star.frame.DispatchHelper")
    cmd = command if command.startswith((".uno:", "macro:", "service:")) else ".uno:" + command
    r = helper.executeDispatch(frame, cmd, "", 0, b.props(**{k: _to_uno(v) for k, v in (arguments or {}).items()}))
    return {"result": _from_uno(r)}


def run_python(code: str, doc_id: str = "") -> dict:
    """Run a Python snippet inside the server with `doc`, `desktop`, `uno`, `props` available; assign `result` to return data. Full local power: use for anything the other tools lack."""
    env = {"uno": uno, "desktop": b.desktop(), "doc": b.doc(doc_id) if doc_id else None, "props": b.props, "bridge": b, "result": None}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<run_python>", "exec"), env)
    except Exception:
        raise b.LOError(traceback.format_exc(limit=3))
    return {"stdout": buf.getvalue(), "result": _from_uno(env.get("result"))}


def run_macro(macro_url: str, args: list = None) -> dict:
    """Run a Basic/Python macro by URL via the script provider, e.g. 'vnd.sun.star.script:Standard.Module1.Main?language=Basic&location=application'."""
    b.desktop()  # make sure the office connection (and b._ctx) exists
    ctx = b._ctx
    prov = ctx.ServiceManager.createInstanceWithContext("com.sun.star.script.provider.MasterScriptProviderFactory", ctx).createScriptProvider("")
    script = prov.getScript(macro_url)
    r = script.invoke(tuple(_to_uno(a) for a in (args or [])), (), ())
    return {"result": _from_uno(r[0])}


def uno_help() -> str:
    """Explain the argument encodings accepted by uno_call/uno_set."""
    return ('Plain JSON for strings/numbers/bools/lists. Special forms: {"handle":"h3"} existing object; '
            '{"enum":"com.sun.star.table.CellHoriJustify.CENTER"}; {"const":"com.sun.star.awt.FontWeight.BOLD"}; '
            '{"struct":"com.sun.star.awt.Size","fields":{"Width":1000,"Height":500}}; '
            '{"props":{"Name":"x"}} for a PropertyValue sequence. Use uno_inspect to discover methods and properties.')


TOOLS = [uno_help, uno_root, uno_create, uno_call, uno_get, uno_set, uno_set_many, uno_inspect, uno_enumerate,
         release_handle, dispatch_command, run_python, run_macro]
