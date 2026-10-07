# Ready-to-use workflows

Pass the complete contents of a workflow JSON file to `workflow_run` in your MCP client. The examples create new documents and save them inside RAJ_WORKSPACE. Existing output filenames require an explicit overwrite decision.

- `workflow-writer.json`: formatted report, table, ODT and PDF.
- `workflow-calc.json`: revenue data, total formula, chart and ODS.
- `workflow-impress.json`: title slide, notes and ODP.

The examples keep documents open after saving so you can continue editing; close them with document_close when finished.
