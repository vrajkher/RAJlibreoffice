"""UNO bridge: launches headless soffice, connects, and tracks documents and object handles."""
import atexit
import os
import subprocess
import threading
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

HOST = os.environ.get("LO_MCP_HOST", "localhost")
PORT = int(os.environ.get("LO_MCP_PORT", "2002"))
SOFFICE = os.environ.get("LO_MCP_SOFFICE", "soffice")
PROFILE = os.environ.get("LO_MCP_PROFILE", "/tmp/lo_mcp_profile")

_lock = threading.RLock()
_proc = None
_desktop = None
_ctx = None
_docs = {}      # id -> model
_handles = {}   # id -> UNO object
_counter = {"doc": 0, "h": 0}


from mcp.server.mcpserver.exceptions import ToolError


class LOError(ToolError):
    """Error reported to the MCP client."""


def props(**kw):
    """Build a tuple of PropertyValue from keyword arguments."""
    out = []
    for k, v in kw.items():
        p = PropertyValue()
        p.Name, p.Value = k, v
        out.append(p)
    return tuple(out)


def to_url(path):
    if path.startswith(("file://", "private:", "http://", "https://", "macro:")):
        return path
    return uno.systemPathToFileUrl(str(Path(path).expanduser().resolve()))


def desktop():
    """Return the connected Desktop, starting soffice if necessary."""
    global _proc, _desktop, _ctx
    with _lock:
        if _desktop is not None:
            try:
                _desktop.getComponents()  # raises if the connection died
                return _desktop
            except Exception:
                _desktop = None
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        url = f"uno:socket,host={HOST},port={PORT};urp;StarOffice.ComponentContext"
        last = None
        for attempt in range(2):
            for _ in range(40 if attempt else 1):
                try:
                    _ctx = resolver.resolve(url)
                    _desktop = _ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", _ctx)
                    return _desktop
                except Exception as e:  # not up yet
                    last = e
                    if attempt:
                        time.sleep(0.5)
            if attempt == 0:
                _proc = subprocess.Popen(
                    [SOFFICE, "--headless", "--invisible", "--norestore", "--nologo", "--nodefault",
                     f"--accept=socket,host={HOST},port={PORT};urp;", f"-env:UserInstallation=file://{PROFILE}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise LOError(f"Cannot connect to LibreOffice on {HOST}:{PORT}: {last}")


@atexit.register
def shutdown():
    global _proc
    if _proc is not None:
        try:
            desktop().terminate()
        except Exception:
            pass
        try:
            _proc.terminate()
        except Exception:
            pass
        _proc = None


def register_doc(model):
    with _lock:
        _counter["doc"] += 1
        did = f"doc{_counter['doc']}"
        _docs[did] = model
        return did


def doc(doc_id):
    try:
        return _docs[doc_id]
    except KeyError:
        raise LOError(f"Unknown document '{doc_id}'. Call list_documents or open_document first.")


def drop_doc(doc_id):
    _docs.pop(doc_id, None)


def all_docs():
    return dict(_docs)


def doc_kind(model):
    for svc, kind in (("com.sun.star.text.TextDocument", "writer"),
                      ("com.sun.star.text.WebDocument", "writer-web"),
                      ("com.sun.star.sheet.SpreadsheetDocument", "calc"),
                      ("com.sun.star.presentation.PresentationDocument", "impress"),
                      ("com.sun.star.drawing.DrawingDocument", "draw"),
                      ("com.sun.star.sdb.OfficeDatabaseDocument", "base"),
                      ("com.sun.star.formula.FormulaProperties", "math")):
        if model.supportsService(svc):
            return kind
    return "unknown"


def need(doc_id, *kinds):
    """Fetch a document and check its kind."""
    m = doc(doc_id)
    k = doc_kind(m)
    if kinds and k not in kinds:
        raise LOError(f"'{doc_id}' is a {k} document; this tool needs {' or '.join(kinds)}.")
    return m


def new_handle(obj):
    with _lock:
        _counter["h"] += 1
        hid = f"h{_counter['h']}"
        _handles[hid] = obj
        return hid


def handle(hid):
    if hid in _docs:
        return _docs[hid]
    try:
        return _handles[hid]
    except KeyError:
        raise LOError(f"Unknown handle '{hid}'.")


def create(service):
    """Instantiate a UNO service in the remote office process."""
    desktop()
    return _ctx.ServiceManager.createInstanceWithContext(service, _ctx)
