from __future__ import annotations

import nbformat

import nb2wb


class TestReverter:
    def test_revert_prose_only_html_to_markdown_cell(self):
        notebook = nb2wb.revert("<html><body><h1>Title</h1><p>Body text.</p></body></html>")

        assert len(notebook.cells) == 1
        assert notebook.cells[0].cell_type == "markdown"
        assert "Title" in notebook.cells[0].source
        assert "Body text." in notebook.cells[0].source
        nbformat.validate(notebook)

    def test_revert_code_block_uses_supported_python_language(self):
        notebook = nb2wb.revert(
            '<html><body><pre><code class="language-python">print("hi")\n</code></pre></body></html>'
        )

        assert notebook.metadata["kernelspec"]["language"] == "python"
        assert notebook.cells[0].cell_type == "code"
        assert notebook.cells[0].metadata["language"] == "python"
        assert 'print("hi")' in notebook.cells[0].source
        nbformat.validate(notebook)

    def test_revert_supported_r_code_block_sets_language_metadata(self):
        notebook = nb2wb.revert(
            '<html><body><pre><code class="language-r">summary(cars)\n</code></pre></body></html>'
        )

        assert notebook.metadata["kernelspec"]["language"] == "r"
        assert notebook.cells[0].cell_type == "code"
        assert notebook.cells[0].metadata["language"] == "r"
        assert "summary(cars)" in notebook.cells[0].source

    def test_revert_unknown_code_block_falls_back_to_markdown_fence(self):
        notebook = nb2wb.revert(
            '<html><body><pre><code class="language-mermaid">graph TD;\nA-->B;\n</code></pre></body></html>'
        )

        assert notebook.metadata["kernelspec"]["language"] == "python"
        assert notebook.cells[0].cell_type == "markdown"
        assert notebook.cells[0].source.startswith("```mermaid")
        assert "graph TD;" in notebook.cells[0].source

    def test_revert_preserves_order_for_mixed_supported_languages(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <pre><code class="language-python">x = 1</code></pre>
              <pre><code class="language-javascript">console.log(x)</code></pre>
            </body></html>
            """
        )

        assert [cell.cell_type for cell in notebook.cells] == ["code", "code"]
        assert notebook.metadata["kernelspec"]["language"] == "python"
        assert notebook.cells[0].metadata["language"] == "python"
        assert notebook.cells[1].metadata["language"] == "javascript"

    def test_revert_defaults_notebook_language_when_no_code_language_detected(self):
        notebook = nb2wb.revert(
            "<html><body><pre><code>unknown syntax</code></pre></body></html>"
        )

        assert notebook.metadata["kernelspec"]["language"] == "python"
        assert notebook.cells[0].cell_type == "markdown"
        assert notebook.cells[0].source.startswith("```")

    def test_revert_keeps_regular_image_in_markdown_flow(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <p>Intro</p>
              <p><img src="plain.png" alt="chart"></p>
              <p>Outro</p>
            </body></html>
            """
        )

        assert len(notebook.cells) == 1
        assert notebook.cells[0].cell_type == "markdown"
        assert "Intro" in notebook.cells[0].source
        assert "![chart](plain.png)" in notebook.cells[0].source
        assert "Outro" in notebook.cells[0].source

    def test_revert_code_image_with_supported_language_defaults_to_linked_figure(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="code-snippet language-python">
                <img src="snippet.png" alt="Python code snippet">
              </figure>
            </body></html>
            """
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "![Python code snippet](snippet.png)" in notebook.cells[0].source

    def test_revert_code_image_without_supported_language_defaults_to_linked_figure(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="code-snippet">
                <img src="snippet.png" alt="terminal screenshot">
              </figure>
            </body></html>
            """
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "![terminal screenshot](snippet.png)" in notebook.cells[0].source

    def test_revert_latex_image_defaults_to_linked_figure(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure>
                <img src="equation.png" alt="LaTeX equation">
              </figure>
            </body></html>
            """
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "![LaTeX equation](equation.png)" in notebook.cells[0].source

    def test_revert_latex_image_uses_ocr_pipeline_output_when_available(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure>
                <img src="equation.png" alt="LaTeX equation">
              </figure>
            </body></html>
            """,
            ocr_pipeline=lambda request: {"type": "latex", "payload": r"\frac{1}{2}"},
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert notebook.cells[0].source == "$$\n\\frac{1}{2}\n$$"
        assert notebook.cells[0].metadata["wb2nb"]["classification"] == "latex"
        assert notebook.cells[0].metadata["wb2nb"]["ocr_type"] == "latex"

    def test_revert_code_image_uses_ocr_pipeline_output_for_code_cell(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="code-snippet language-python">
                <img src="snippet.png" alt="Python code snippet">
              </figure>
            </body></html>
            """,
            ocr_pipeline=lambda request: {"type": "code", "payload": "print(42)"},
        )

        assert notebook.cells[0].cell_type == "code"
        assert notebook.cells[0].source == "print(42)"
        assert notebook.cells[0].metadata["language"] == "python"
        assert notebook.cells[0].metadata["wb2nb"]["ocr_type"] == "code"

    def test_revert_passes_image_context_into_ocr_pipeline(self):
        seen: dict[str, object] = {}

        def pipeline(request):
            seen["request"] = request
            return {"type": "figure", "payload": ""}

        nb2wb.revert(
            """
            <html><body>
              <figure class="code-snippet language-python">
                <img src="snippet.png" alt="Python code snippet" title="Snippet">
                <figcaption>Example caption</figcaption>
              </figure>
            </body></html>
            """,
            ocr_pipeline=pipeline,
        )

        request = seen["request"]
        assert request.src == "snippet.png"
        assert request.alt == "Python code snippet"
        assert request.title == "Snippet"
        assert request.caption == "Example caption"
        assert request.classes == ("code-snippet", "language-python")

    def test_revert_table_image_uses_ocr_pipeline_output_for_markdown_cell(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="table">
                <img src="table.png" alt="Model comparison table">
              </figure>
            </body></html>
            """,
            ocr_pipeline=lambda request: {"type": "table", "payload": "|A|B|\n|-|-|\n|1|2|"},
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert notebook.cells[0].source == "|A|B|\n|-|-|\n|1|2|"
        assert notebook.cells[0].metadata["wb2nb"]["ocr_type"] == "table"

    def test_revert_figure_ocr_result_keeps_image_linked_in_markdown(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="table">
                <img src="figure.png" alt="Chart figure">
              </figure>
            </body></html>
            """,
            ocr_pipeline=lambda request: {"type": "figure", "payload": ""},
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "![Chart figure](figure.png)" in notebook.cells[0].source

    def test_revert_rejects_invalid_ocr_result(self):
        try:
            nb2wb.revert(
                "<html><body><figure><img src='equation.png' alt='LaTeX equation'></figure></body></html>",
                ocr_pipeline=lambda request: {"type": "bogus", "payload": ""},
            )
        except ValueError as exc:
            assert "ocr_pipeline result 'type' must be one of" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected invalid OCR result to raise ValueError")

    def test_revert_table_image_defaults_to_linked_figure(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure class="table">
                <img src="table.png" alt="Model comparison table">
              </figure>
            </body></html>
            """
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "![Model comparison table](table.png)" in notebook.cells[0].source

    def test_revert_bare_figure_does_not_crash_and_preserves_text(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <figure>
                <figcaption>Caption only</figcaption>
              </figure>
            </body></html>
            """
        )

        assert notebook.cells[0].cell_type == "markdown"
        assert "Caption only" in notebook.cells[0].source

    def test_revert_content_root_falls_back_to_document_when_body_missing(self):
        notebook = nb2wb.revert("<div><p>Fallback root content</p></div>")

        assert notebook.cells[0].cell_type == "markdown"
        assert "Fallback root content" in notebook.cells[0].source

    def test_revert_accepts_html_mapping_payload(self):
        notebook = nb2wb.revert({"format": "html", "content": "<p>Hello</p>"})

        assert notebook.cells[0].cell_type == "markdown"
        assert "Hello" in notebook.cells[0].source
        assert notebook.metadata["wb2nb"]["source_format"] == "html"
