"""Document lifecycle: open, create, save, export, close, inspect."""
import os

from .. import bridge as b

NEW_URLS = {
    "writer": "private:factory/swriter", "calc": "private:factory/scalc",
    "impress": "private:factory/simpress", "draw": "private:factory/sdraw",
    "base": "private:factory/sdatabase", "math": "private:factory/smath",
}
# export filter names by file extension, per document kind
FILTERS = {
    "pdf": {"writer": "writer_pdf_Export", "calc": "calc_pdf_Export", "impress": "impress_pdf_Export", "draw": "draw_pdf_Export", "math": "math_pdf_Export"},
    "docx": {"writer": "MS Word 2007 XML"}, "doc": {"writer": "MS Word 97"}, "odt": {"writer": "writer8"},
    "rtf": {"writer": "Rich Text Format"}, "txt": {"writer": "Text (encoded)"}, "html": {"writer": "HTML (StarWriter)", "calc": "HTML (StarCalc)", "impress": "impress_html_Export"},
    "epub": {"writer": "EPUB"}, "xlsx": {"calc": "Calc MS Excel 2007 XML"}, "xls": {"calc": "MS Excel 97"}, "ods": {"calc": "calc8"},
    "csv": {"calc": "Text - txt - csv (StarCalc)"}, "pptx": {"impress": "Impress MS PowerPoint 2007 XML"}, "ppt": {"impress": "MS PowerPoint 97"},
    "odp": {"impress": "impress8"}, "odg": {"draw": "draw8"}, "odb": {"base": "StarOffice XML (Base)"}, "odf": {"math": "math8"},
    "png": {"impress": "impress_png_Export", "draw": "draw_png_Export", "writer": "writer_png_Export", "calc": "calc_png_Export"},
    "jpg": {"impress": "impress_jpg_Export", "draw": "draw_jpg_Export"}, "svg": {"impress": "impress_svg_Export", "draw": "draw_svg_Export"},
}


def open_document(path: str, read_only: bool = False, password: str = "") -> dict:
    """Open an existing file (any format LibreOffice reads) and return its doc_id."""
    if not os.path.exists(os.path.expanduser(path)) and "://" not in path:
        raise b.LOError(f"File not found: {path}")
    kw = {"Hidden": True, "ReadOnly": read_only}
    if password:
        kw["Password"] = password
    m = b.desktop().loadComponentFromURL(b.to_url(path), "_blank", 0, b.props(**kw))
    if m is None:
        raise b.LOError(f"LibreOffice could not open {path}")
    return {"doc_id": b.register_doc(m), "kind": b.doc_kind(m), "title": m.getTitle()}


def create_document(kind: str = "writer") -> dict:
    """Create a blank document. kind: writer | calc | impress | draw | base | math."""
    if kind not in NEW_URLS:
        raise b.LOError(f"kind must be one of {sorted(NEW_URLS)}")
    try:
        m = b.desktop().loadComponentFromURL(NEW_URLS[kind], "_blank", 0, b.props(Hidden=True))
    except Exception as e:
        if "type detection failed" in str(e):
            raise b.LOError(f"This LibreOffice install lacks the {kind} module (Debian/Ubuntu: apt install libreoffice-{kind}).")
        raise
    return {"doc_id": b.register_doc(m), "kind": kind}


def list_documents() -> list:
    """List documents opened through this server."""
    return [{"doc_id": k, "kind": b.doc_kind(m), "title": m.getTitle(), "url": m.getURL(), "modified": m.isModified()}
            for k, m in b.all_docs().items()]


def save_document(doc_id: str) -> dict:
    """Save in place (the document must already have a location; otherwise use save_document_as)."""
    m = b.doc(doc_id)
    if not m.hasLocation():
        raise b.LOError("Document has no file location yet; use save_document_as.")
    m.store()
    return {"saved": m.getURL()}


def save_document_as(doc_id: str, path: str, format: str = "") -> dict:
    """Save a copy to path. The format is inferred from the extension (docx, xlsx, pptx, odt, ods, odp, pdf, csv, html, ...) or given explicitly."""
    m = b.doc(doc_id)
    ext = (format or os.path.splitext(path)[1].lstrip(".")).lower()
    kind = b.doc_kind(m)
    flt = FILTERS.get(ext, {}).get(kind)
    if ext and flt is None and ext not in ("odt", "ods", "odp", "odg"):
        raise b.LOError(f"No export filter for .{ext} from a {kind} document. Known: {sorted(e for e, f in FILTERS.items() if kind in f)}")
    kw = {"FilterName": flt} if flt else {}
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(path))), exist_ok=True)
    url = b.to_url(path)
    if ext in ("pdf", "png", "jpg", "svg", "csv", "html", "txt", "epub"):
        m.storeToURL(url, b.props(**kw))          # export only; document keeps its identity
    else:
        m.storeAsURL(url, b.props(**kw))
    return {"saved": url, "filter": flt}


def export_pdf(doc_id: str, path: str, page_range: str = "", password: str = "") -> dict:
    """Export to PDF with optional page range (e.g. '1-3,5') and open password."""
    m = b.doc(doc_id)
    fd = {}
    if page_range:
        fd["PageRange"] = page_range
    if password:
        fd["EncryptFile"] = True
        fd["DocumentOpenPassword"] = password
    kw = {"FilterName": FILTERS["pdf"][b.doc_kind(m)]}
    if fd:
        kw["FilterData"] = b.uno.Any("[]com.sun.star.beans.PropertyValue", b.props(**fd))
    m.storeToURL(b.to_url(path), b.props(**kw))
    return {"saved": b.to_url(path)}


def close_document(doc_id: str, discard_changes: bool = True) -> dict:
    """Close a document. Unsaved changes are discarded unless discard_changes is False (then it errors if modified)."""
    m = b.doc(doc_id)
    if m.isModified() and not discard_changes:
        raise b.LOError("Document has unsaved changes; save it or pass discard_changes=true.")
    m.close(True)
    b.drop_doc(doc_id)
    return {"closed": doc_id}


def document_info(doc_id: str) -> dict:
    """Metadata and statistics: title, author, subject, keywords, counts and kind-specific stats."""
    m = b.doc(doc_id)
    p = m.getDocumentProperties()
    info = {"doc_id": doc_id, "kind": b.doc_kind(m), "url": m.getURL(), "modified": m.isModified(),
            "title": p.Title, "author": p.Author, "subject": p.Subject, "keywords": list(p.Keywords), "description": p.Description}
    k = info["kind"]
    if k == "writer":
        st = {}
        for n in ("CharacterCount", "WordCount", "ParagraphCount"):
            st[n] = m.getPropertyValue(n)
        try:
            st["PageCount"] = m.getCurrentController().getPropertyValue("PageCount")
        except Exception:
            pass
        info["stats"] = st
    elif k == "calc":
        info["sheets"] = list(m.Sheets.ElementNames)
    elif k in ("impress", "draw"):
        info["pages"] = m.DrawPages.Count
    return info


def set_document_properties(doc_id: str, title: str = None, author: str = None, subject: str = None,
                            keywords: list = None, description: str = None) -> dict:
    """Set document metadata."""
    p = b.doc(doc_id).getDocumentProperties()
    for name, val in (("Title", title), ("Author", author), ("Subject", subject), ("Description", description)):
        if val is not None:
            setattr(p, name, val)
    if keywords is not None:
        p.Keywords = tuple(keywords)
    return {"ok": True}


def undo_redo(doc_id: str, action: str = "undo", steps: int = 1) -> dict:
    """Undo or redo the last edits. action: undo | redo."""
    um = b.doc(doc_id).getUndoManager()
    for _ in range(steps):
        (um.undo if action == "undo" else um.redo)()
    return {"ok": True}


def supported_export_formats(doc_id: str) -> list:
    """List export extensions available for this document."""
    k = b.doc_kind(b.doc(doc_id))
    return sorted(e for e, f in FILTERS.items() if k in f)


TOOLS = [open_document, create_document, list_documents, save_document, save_document_as, export_pdf,
         close_document, document_info, set_document_properties, undo_redo, supported_export_formats]
