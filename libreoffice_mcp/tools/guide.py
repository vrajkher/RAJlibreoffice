"""Step-by-step workflow guide so any client can use the server without guessing."""

GUIDE = {
    "start": """LibreOffice MCP workflow (always the same 5 steps)
1. OPEN    create_document(kind) or open_document(path)  -> doc_id
2. LOOK    document_info(doc_id), then writer_get_text / calc_get_range / impress_list_slides
3. EDIT    use the writer_*, calc_*, impress_* (also draw) tools with the doc_id
4. VERIFY  read back what you changed; export_pdf for a visual check
5. SAVE    save_document_as(doc_id, path) (format from extension), then close_document

Need something without a dedicated tool? uno_root -> uno_inspect -> uno_call/uno_set, dispatch_command('.uno:...'), or run_python.
Topics: lo_guide('writer'|'calc'|'impress'|'draw'|'base'|'math'|'uno'|'tips')""",
    "writer": "Writer: writer_get_text, writer_set_text, writer_append, writer_insert_paragraph(style=), writer_find_replace, writer_list_paragraphs, writer_format_range, writer_insert_table/set_table_cell/get_table, writer_insert_image, writer_page_setup, writer_header_footer, writer_toc, writer_bookmark, writer_comment, writer_track_changes, writer_footnote, writer_list_styles, writer_apply_style.",
    "calc": "Calc: calc_sheets, calc_add_sheet, calc_get_range, calc_set_range (values or '=formulas'), calc_format_range, calc_merge, calc_named_range, calc_chart, calc_sort, calc_autofilter, calc_validation, calc_conditional_format, calc_freeze, calc_col_row_size, calc_pivot, calc_recalculate, calc_find_replace. Ranges use A1 notation like 'Sheet1.A1:C10' or 'A1:C10' with sheet=.",
    "impress": "Impress/Draw: impress_list_slides, impress_add_slide, impress_delete_slide, impress_add_shape, impress_add_text, impress_add_image, impress_list_shapes, impress_edit_shape, impress_delete_shape, impress_set_layout, impress_notes, impress_transition, impress_master, impress_export_slide.",
    "draw": "Draw uses the impress_* tools (pages = slides). Shapes: rectangle, ellipse, line, polygon, text, connector, custom.",
    "base": "Base: base_open, base_tables, base_query (SELECT/INSERT/UPDATE via SQL), base_create_table.",
    "math": "Math: math_set_formula(doc_id, 'a over b'), math_insert_into(doc_id, target_doc_id) embeds a formula into Writer.",
    "uno": "UNO: handles are strings like h3. uno_root(doc,'text') -> uno_inspect(h) -> uno_call(h,'method',[args]). Special arg forms: see uno_help.",
    "tips": "Colours are 0xRRGGBB ints or '#RRGGBB'. Lengths are 1/100 mm. Page/row/column indices are 0-based unless a tool says otherwise. Check tool errors: they name what is missing.",
}


def lo_guide(topic: str = "start") -> str:
    """START HERE. Returns the step-by-step workflow and the tool list for a topic: start | writer | calc | impress | draw | base | math | uno | tips."""
    return GUIDE.get(topic, f"Unknown topic. Choose from: {', '.join(GUIDE)}")


TOOLS = [lo_guide]
