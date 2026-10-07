# How to use LibreOffice MCP

Each recipe is the flow the assistant follows. You only need to ask in plain words; the tool names are shown so you can see what happens.

**Golden rules**
- Every document has a `doc_id` (like `doc1`). Pass it to each tool.
- Positions are 0-based (first slide = 0, first paragraph = 0). Cell ranges use normal spreadsheet notation: `A1:C10`, `Sheet2.B3`.
- Lengths in the friendly tools are millimetres. Colours are `#RRGGBB` or names like `red`.
- Always finish with **save**. Nothing is written to disk until `save_document_as`.

---

## Recipe 1: Write a report (Writer)

```
create_document(kind="writer")                         → doc1
writer_append(doc1, "Q3 Report", style="Heading 1")
writer_append(doc1, "Revenue grew 12%…", style="Text Body")
writer_insert_table(doc1, data=[["Region","Sales"],["North",120],["South",95]])
writer_format_range(doc1, search="Revenue", bold=true)
writer_header_footer(doc1, header="Acme", page_numbers="footer")
writer_toc(doc1)                                       # table of contents
save_document_as(doc1, "~/q3.docx")
export_pdf(doc1, "~/q3.pdf")
```

Edit an existing file: `open_document("~/letter.docx")`, `writer_find_replace(doc, "Dear Sir", "Dear Ms Lee")`, `save_document`.

## Recipe 2: Build a spreadsheet (Calc)

```
create_document(kind="calc")                           → doc1
calc_set_range(doc1, "A1", [["Item","Qty","Price"],["Pen",10,1.5],["Book",3,12]])
calc_set_cell(doc1, "D1", "Total")
calc_set_range(doc1, "D2", [["=B2*C2"],["=B3*C3"]])
calc_format_range(doc1, "A1:D1", bold=true, color_bg="#DDDDDD")
calc_format_range(doc1, "C2:D3", number_format="$#,##0.00")
calc_chart(doc1, "A1:B3", kind="column", title="Quantities")
calc_get_range(doc1, "A1:D3")                          # verify the computed values
save_document_as(doc1, "~/stock.xlsx")
```

More: `calc_sort`, `calc_autofilter`, `calc_validation` (dropdown lists), `calc_conditional_format`, `calc_pivot`, `calc_freeze`.

## Recipe 3: Make a presentation (Impress)

```
create_document(kind="impress")                        → doc1
impress_add_slide(doc1, "title_content", title="Roadmap", body="Q1 launch\nQ2 scale")
impress_add_shape(doc1, 1, "star", x_mm=200, y_mm=20, w_mm=40, h_mm=40, fill="yellow")
impress_add_image(doc1, 1, "~/logo.png", x_mm=10, y_mm=10, w_mm=30)
impress_notes(doc1, 1, "Mention the launch date")
impress_transition(doc1, 1, "DISSOLVE")
impress_export_slide(doc1, 1, "~/slide2.png")           # visual check
save_document_as(doc1, "~/roadmap.pptx")
```

Draw documents use the same `impress_*` tools (a page is a slide).

## Recipe 4: Convert files

```
open_document("~/report.docx")  → doc1
save_document_as(doc1, "~/report.pdf")        # or .odt .rtf .html .epub
```

Spreadsheet to CSV: `save_document_as(doc, "~/data.csv")`. Slides to images: `impress_export_slide` per slide. See what a document can export to with `supported_export_formats(doc_id)`.

## Recipe 5: Anything else (generic UNO)

If no tool fits, discover and call the LibreOffice API directly:

```
uno_root(doc1, "text")              → {"handle": "h1"}
uno_inspect("h1")                   # lists properties and methods
uno_call("h1", "setString", ["Hello"])
uno_set("h1", "CharHeight", 18)
dispatch_command(doc1, ".uno:SelectAll")
```

`uno_help()` explains how to pass enums, structs and other objects. `run_python` runs a snippet with `doc`, `desktop` and `uno` ready to use.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Cannot connect to LibreOffice" | Check `soffice --version` works; free the port (`LO_MCP_PORT`) or kill stray `soffice` processes |
| `ModuleNotFoundError: uno` | Run with the system `python3`, with `python3-uno` installed |
| "Unknown document 'docN'" | The id is wrong or it was closed. Call `list_documents` |
| "No Paragraph style …" | Call `writer_list_styles`; names like "Heading 1" and "Text Body" are accepted, case-insensitive |
| "lacks the math/base module" | `sudo apt install libreoffice-math libreoffice-base` |
| Slideshow won't start | Needs a visible window; use `impress_export_slide` instead |
