from __future__ import annotations

import nbformat
from pathlib import Path
import sys

from nb2wb.revert_cli import main


def _invoke_cli(argv: list[str]) -> None:
    sys.argv = argv
    main()


def _run_cli(argv: list[str]) -> None:
    try:
        _invoke_cli(argv)
    except SystemExit:
        pass


class TestRevertCli:
    def test_wb2nb_writes_default_output_path(self, tmp_path: Path):
        html_path = tmp_path / "post.html"
        html_path.write_text(
            '<html><body><pre><code class="language-python">print("hi")</code></pre></body></html>',
            encoding="utf-8",
        )

        _run_cli(["wb2nb", str(html_path)])

        output_path = tmp_path / "post.ipynb"
        assert output_path.exists()

        with output_path.open("r", encoding="utf-8") as handle:
            notebook = nbformat.read(handle, as_version=nbformat.NO_CONVERT)

        assert notebook.cells[0].cell_type == "code"
        assert notebook.cells[0].metadata["language"] == "python"
        assert notebook.metadata["wb2nb"]["source_format"] == "html"

    def test_wb2nb_uses_default_api_revert_signature(self, tmp_path: Path, monkeypatch):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}

        def fake_revert(document, *, ocr_pipeline=None, verbose=False):
            seen["document"] = document
            seen["ocr_pipeline"] = ocr_pipeline
            seen["verbose"] = verbose
            return nbformat.v4.new_notebook()

        monkeypatch.setattr("nb2wb.revert_cli.revert", fake_revert)

        _run_cli(["wb2nb", str(html_path)])

        assert seen["ocr_pipeline"] is None
        assert seen["verbose"] is False
        assert isinstance(seen["document"], dict)
        assert seen["document"]["format"] == "html"

    def test_wb2nb_local_ocr_pipeline_is_opt_in(self, tmp_path: Path, monkeypatch):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}
        sentinel = object()

        def fake_revert(document, *, ocr_pipeline=None, verbose=False):
            seen["ocr_pipeline"] = ocr_pipeline
            return nbformat.v4.new_notebook()

        monkeypatch.setattr("nb2wb.revert_cli.local_ocr_pipeline", sentinel)
        monkeypatch.setattr("nb2wb.revert_cli.revert", fake_revert)

        _run_cli(["wb2nb", str(html_path), "--ocr-pipeline", "local"])

        assert seen["ocr_pipeline"] is sentinel

    def test_wb2nb_openai_requires_model(self, tmp_path: Path, monkeypatch, capsys):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        try:
            _invoke_cli(["wb2nb", str(html_path), "--ocr-pipeline", "openai"])
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover
            raise AssertionError("expected parser error for missing --model")

        captured = capsys.readouterr()
        assert "--model is required" in captured.err

    def test_wb2nb_openai_requires_openai_api_key(self, tmp_path: Path, monkeypatch, capsys):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        try:
            _invoke_cli(
                [
                    "wb2nb",
                    str(html_path),
                    "--ocr-pipeline",
                    "openai",
                    "--model",
                    "gpt-4.1-mini",
                ]
            )
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover
            raise AssertionError("expected parser error for missing OPENAI_API_KEY")

        captured = capsys.readouterr()
        assert "OPENAI_API_KEY environment variable is required" in captured.err

    def test_wb2nb_openai_constructs_pipeline_and_passes_to_api(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}
        sentinel = object()

        class FakePipeline:
            def __init__(
                self,
                *,
                model,
                api_key=None,
                client=None,
                verbose=False,
                allow_remote_image_urls=True,
            ):
                seen["model"] = model
                seen["api_key"] = api_key
                seen["client"] = client
                seen["verbose"] = verbose
                seen["allow_remote_image_urls"] = allow_remote_image_urls

            def __call__(self, request):
                return sentinel

        def fake_revert(document, *, ocr_pipeline=None, verbose=False):
            seen["document"] = document
            seen["ocr_pipeline"] = ocr_pipeline
            seen["verbose"] = verbose
            return nbformat.v4.new_notebook()

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr("nb2wb.revert_cli.OpenAIOCRPipeline", FakePipeline)
        monkeypatch.setattr("nb2wb.revert_cli.revert", fake_revert)

        _run_cli(
            [
                "wb2nb",
                str(html_path),
                "--ocr-pipeline",
                "openai",
                "--model",
                "gpt-4.1-mini",
            ]
        )

        assert seen["model"] == "gpt-4.1-mini"
        assert seen["api_key"] is None
        assert seen["verbose"] is False
        assert seen["allow_remote_image_urls"] is True
        assert isinstance(seen["document"], dict)
        assert isinstance(seen["ocr_pipeline"], FakePipeline)
        assert seen["verbose"] is False

    def test_wb2nb_gemini_requires_model(self, tmp_path: Path, monkeypatch, capsys):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        try:
            _invoke_cli(["wb2nb", str(html_path), "--ocr-pipeline", "gemini"])
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover
            raise AssertionError("expected parser error for missing --model")

        captured = capsys.readouterr()
        assert "--model is required" in captured.err

    def test_wb2nb_gemini_requires_gemini_or_google_api_key(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        try:
            _invoke_cli(
                [
                    "wb2nb",
                    str(html_path),
                    "--ocr-pipeline",
                    "gemini",
                    "--model",
                    "gemini-2.0-flash",
                ]
            )
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover
            raise AssertionError(
                "expected parser error for missing GEMINI_API_KEY/GOOGLE_API_KEY"
            )

        captured = capsys.readouterr()
        assert "GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required" in (
            captured.err
        )

    def test_wb2nb_gemini_constructs_pipeline_and_passes_to_api(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}
        sentinel = object()

        class FakePipeline:
            def __init__(
                self,
                *,
                model,
                api_key=None,
                client=None,
                verbose=False,
                allow_remote_image_urls=True,
            ):
                seen["model"] = model
                seen["api_key"] = api_key
                seen["client"] = client
                seen["verbose"] = verbose
                seen["allow_remote_image_urls"] = allow_remote_image_urls

            def __call__(self, request):
                return sentinel

        def fake_revert(document, *, ocr_pipeline=None, verbose=False):
            seen["document"] = document
            seen["ocr_pipeline"] = ocr_pipeline
            seen["verbose"] = verbose
            return nbformat.v4.new_notebook()

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("nb2wb.revert_cli.GeminiOCRPipeline", FakePipeline)
        monkeypatch.setattr("nb2wb.revert_cli.revert", fake_revert)

        _run_cli(
            [
                "wb2nb",
                str(html_path),
                "--ocr-pipeline",
                "gemini",
                "--model",
                "gemini-2.0-flash",
            ]
        )

        assert seen["model"] == "gemini-2.0-flash"
        assert seen["api_key"] is None
        assert seen["verbose"] is False
        assert seen["allow_remote_image_urls"] is True
        assert isinstance(seen["document"], dict)
        assert isinstance(seen["ocr_pipeline"], FakePipeline)
        assert seen["verbose"] is False

    def test_wb2nb_gemini_passes_verbose_flag_to_pipeline(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}

        class FakePipeline:
            def __init__(
                self,
                *,
                model,
                api_key=None,
                client=None,
                verbose=False,
                allow_remote_image_urls=True,
            ):
                seen["model"] = model
                seen["verbose"] = verbose
                seen["allow_remote_image_urls"] = allow_remote_image_urls

            def __call__(self, request):
                return {"type": "figure", "payload": ""}

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("nb2wb.revert_cli.GeminiOCRPipeline", FakePipeline)
        monkeypatch.setattr(
            "nb2wb.revert_cli.revert",
            lambda document, *, ocr_pipeline=None, verbose=False: nbformat.v4.new_notebook(),
        )

        _run_cli(
            [
                "wb2nb",
                str(html_path),
                "--ocr-pipeline",
                "gemini",
                "--model",
                "gemini-2.0-flash",
                "--verbose",
            ]
        )

        assert seen["model"] == "gemini-2.0-flash"
        assert seen["verbose"] is True
        assert seen["allow_remote_image_urls"] is True

    def test_wb2nb_openai_disallow_remote_image_urls_overrides_default(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}

        class FakePipeline:
            def __init__(
                self,
                *,
                model,
                api_key=None,
                client=None,
                verbose=False,
                allow_remote_image_urls=True,
            ):
                seen["allow_remote_image_urls"] = allow_remote_image_urls

            def __call__(self, request):
                return {"type": "figure", "payload": ""}

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr("nb2wb.revert_cli.OpenAIOCRPipeline", FakePipeline)
        monkeypatch.setattr(
            "nb2wb.revert_cli.revert",
            lambda document, *, ocr_pipeline=None, verbose=False: nbformat.v4.new_notebook(),
        )

        _run_cli(
            [
                "wb2nb",
                str(html_path),
                "--ocr-pipeline",
                "openai",
                "--model",
                "gpt-4.1-mini",
                "--disallow-remote-image-urls",
            ]
        )

        assert seen["allow_remote_image_urls"] is False

    def test_wb2nb_gemini_disallow_remote_image_urls_overrides_default(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}

        class FakePipeline:
            def __init__(
                self,
                *,
                model,
                api_key=None,
                client=None,
                verbose=False,
                allow_remote_image_urls=True,
            ):
                seen["allow_remote_image_urls"] = allow_remote_image_urls

            def __call__(self, request):
                return {"type": "figure", "payload": ""}

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr("nb2wb.revert_cli.GeminiOCRPipeline", FakePipeline)
        monkeypatch.setattr(
            "nb2wb.revert_cli.revert",
            lambda document, *, ocr_pipeline=None, verbose=False: nbformat.v4.new_notebook(),
        )

        _run_cli(
            [
                "wb2nb",
                str(html_path),
                "--ocr-pipeline",
                "gemini",
                "--model",
                "gemini-2.0-flash",
                "--disallow-remote-image-urls",
            ]
        )

        assert seen["allow_remote_image_urls"] is False

    def test_wb2nb_passes_verbose_flag_to_api(self, tmp_path: Path, monkeypatch):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
        seen: dict[str, object] = {}

        def fake_revert(document, *, ocr_pipeline=None, verbose=False):
            seen["verbose"] = verbose
            return nbformat.v4.new_notebook()

        monkeypatch.setattr("nb2wb.revert_cli.revert", fake_revert)

        _run_cli(["wb2nb", str(html_path), "--verbose"])

        assert seen["verbose"] is True
