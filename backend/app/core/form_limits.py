"""Allow larger multipart text fields than Starlette's 1 MB default.

The widget sends the whole Excalidraw scene as the `scene_json` form field,
including inserted images as base64 data URLs. A worksheet image easily makes
that field bigger than 1 MB, and Starlette then rejects the request with
"Part exceeded maximum size of 1024KB." before /api/chat even runs.

FastAPI parses forms with `await request.form()` and offers no setting for the
limit, so the default is raised here once, at startup.
"""
from starlette.requests import Request

MAX_FORM_PART_BYTES = 25 * 1024 * 1024   # 25 MB per field

_original_form = Request.form


def _form_with_larger_parts(self, *, max_files=1000, max_fields=1000,
                            max_part_size=MAX_FORM_PART_BYTES):
    return _original_form(self, max_files=max_files, max_fields=max_fields,
                          max_part_size=max_part_size)


def raise_form_part_limit() -> None:
    """Idempotent: safe to call more than once."""
    if Request.form is not _form_with_larger_parts:
        Request.form = _form_with_larger_parts
