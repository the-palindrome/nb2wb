from __future__ import annotations

import nbformat

import nb2wb

_VIDEO_MEDIA_UPLOAD_ID = "35dd1111-2222-3333-4444-555566667777"
_VIDEO_PLACEHOLDER_FIXTURE = (
    '<div class="native-video-embed" data-component-name="VideoPlaceholder" '
    'data-attrs="{&quot;mediaUploadId&quot;:&quot;'
    f"{_VIDEO_MEDIA_UPLOAD_ID}"
    '&quot;,&quot;duration&quot;:null}"></div>'
)


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

    def test_revert_native_video_placeholder_emits_video_html_and_fallback_link(self):
        notebook = nb2wb.revert(
            {
                "format": "html",
                "content": f"<html><body>{_VIDEO_PLACEHOLDER_FIXTURE}</body></html>",
                "source_origin": "example.substack.com/path/ignored",
            }
        )

        expected_url = (
            "https://example.substack.com"
            f"/api/v1/video/upload/{_VIDEO_MEDIA_UPLOAD_ID}/src?type=mp4"
        )

        assert len(notebook.cells) == 1
        assert notebook.cells[0].cell_type == "markdown"
        assert f'<video controls preload="metadata" playsinline src="{expected_url}"></video>' in notebook.cells[0].source
        assert f"[Open video]({expected_url})" in notebook.cells[0].source

    def test_revert_preserves_existing_video_and_source_tags_in_markdown_output(self):
        notebook = nb2wb.revert(
            """
            <html><body>
              <p>Intro</p>
              <video controls preload="metadata" playsinline>
                <source src="https://cdn.example.com/video.mp4" type="video/mp4">
              </video>
              <p>Outro</p>
            </body></html>
            """
        )

        source = notebook.cells[0].source
        assert notebook.cells[0].cell_type == "markdown"
        assert "Intro" in source
        assert "Outro" in source
        assert "<video" in source
        assert 'preload="metadata"' in source
        assert "<source" in source
        assert 'src="https://cdn.example.com/video.mp4"' in source

    def test_revert_video_placeholder_without_media_upload_id_does_not_crash(self):
        notebook = nb2wb.revert(
            {
                "format": "html",
                "content": (
                    "<html><body>"
                    '<div class="native-video-embed" data-component-name="VideoPlaceholder" '
                    'data-attrs="{&quot;duration&quot;:null}"></div>'
                    "</body></html>"
                ),
                "source_origin": "https://example.substack.com",
            }
        )

        assert notebook.cells == []

    def test_revert_non_video_imports_are_unchanged_when_source_origin_is_provided(self):
        html = "<html><body><h1>Title</h1><p>Body text.</p></body></html>"

        baseline = nb2wb.revert(html)
        with_source_origin = nb2wb.revert(
            {
                "format": "html",
                "content": html,
                "source_origin": "https://example.substack.com",
            }
        )

        assert [cell.cell_type for cell in with_source_origin.cells] == [
            cell.cell_type for cell in baseline.cells
        ]
        assert [cell.source for cell in with_source_origin.cells] == [cell.source for cell in baseline.cells]
        assert with_source_origin.metadata["kernelspec"]["language"] == baseline.metadata["kernelspec"]["language"]

    def test_revert_skips_image_transcription_when_no_pipeline_is_given(self):
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
        assert notebook.cells[0].source == "![Model comparison table](table.png)"
        assert "wb2nb" not in notebook.cells[0].metadata

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
