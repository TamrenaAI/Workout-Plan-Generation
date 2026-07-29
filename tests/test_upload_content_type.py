"""
Tests for api.routes.plan._read_as_image's content-type handling.

Real browsers have no built-in MIME mapping for .jfif (a common format for
InBody scans saved via Windows' screenshot/save tools) and report it as the
generic `application/octet-stream` instead of `image/jfif` — so trusting the
browser-reported Content-Type alone rejected every .jfif upload with a 415,
even though SUPPORTED_CONTENT_TYPES was written as if `image/jfif` would show
up. _read_as_image now falls back to the filename extension when the
reported content type isn't recognized.
"""

import asyncio
import io
import os
import sys

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes.plan import _read_as_image


def _upload(filename: str, content_type: str, body: bytes = b"fake-image-bytes") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_jfif_with_octet_stream_content_type_is_accepted():
    upload = _upload("inbody_scan.jfif", "application/octet-stream")
    image_bytes, content_type = asyncio.run(_read_as_image(upload))
    assert content_type == "image/jpeg"
    assert image_bytes == b"fake-image-bytes"


def test_jpg_with_octet_stream_content_type_is_accepted():
    upload = _upload("scan.jpg", "application/octet-stream")
    _, content_type = asyncio.run(_read_as_image(upload))
    assert content_type == "image/jpeg"


def test_recognized_content_type_is_still_trusted_over_extension():
    upload = _upload("scan.png", "image/jpeg")
    _, content_type = asyncio.run(_read_as_image(upload))
    assert content_type == "image/jpeg"


def test_unrecognized_type_and_extension_still_rejected():
    upload = _upload("notes.txt", "application/octet-stream")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_read_as_image(upload))
    assert exc_info.value.status_code == 415
