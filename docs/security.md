# Security Model

This page describes the built-in protections and the trust boundaries you still need to enforce at deployment time.

## High-Level Guarantees

`nb2wb` enforces a mandatory server-safe pipeline during conversion.

Built-in protections include:

- strict HTML/SVG sanitization
- CSS URL sanitization
- SSRF checks for remote image fetching
- local image path traversal checks
- fail-closed image embedding behavior
- notebook resource limits (input size, cell count, output size, LaTeX workload)

## Notebook Execution Boundary

Execution is disabled by default.

If you enable execution (`--execute` or `execute=True`):

- notebook code is untrusted code
- run in isolated worker processes/containers
- enforce process-level CPU/memory/time limits
- avoid running with broad filesystem or network access

## LaTeX Rendering Safety

Display math rendering always runs.

Safety controls include:

- TeX input sanitization before subprocess launch
- blocked dangerous TeX commands/packages
- explicit `-no-shell-escape`
- subprocess timeouts

## HTML / SVG Sanitization

Notebook-provided rich outputs and generated markdown HTML are sanitized.

Sanitizer behavior:

- strips dangerous tags and event handler attributes
- blocks dangerous URI schemes
- sanitizes style attributes and `<style>` blocks
- restricts CSS `url(...)` to fragment refs and data image URIs

## Image Fetching and SSRF

When converting external image URLs:

- only `http/https` allowed
- rejects non-public and loopback/private ranges
- validates redirect targets
- enforces download timeout and size limit
- checks MIME type allowlist

Local file image handling also blocks:

- absolute paths
- `..` traversal
- symlink escapes outside working directory

## Resource Limits

The safety config enforces limits such as:

- `max_input_bytes`
- `max_cells`
- `max_cell_source_chars`
- `max_total_output_bytes`
- `max_display_math_blocks`
- `max_total_latex_chars`

Tune these in high-load deployments based on expected notebook size.

## Recommended Deployment Controls

For backend services, add:

- request body size limits at reverse proxy/API layer
- per-request timeout and cancellation
- queue/concurrency limits
- isolated runtime for execute-enabled jobs
- structured logging and job-level audit trail
