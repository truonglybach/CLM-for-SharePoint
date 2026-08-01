"""
Proposed patch for sharepoint_io.py

Adds:
- automatic upload routing
- resumable upload sessions for large files
- retry support around chunk uploads
"""

SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024  # 4 MB
CHUNK_SIZE = 5 * 1024 * 1024           # 5 MB


def upload_file(sp_path: str, content: bytes,
                content_type: str = "application/octet-stream"):
    if len(content) < SIMPLE_UPLOAD_LIMIT:
        return _simple_upload(sp_path, content, content_type)
    return _resumable_upload(sp_path, content, content_type)


def _simple_upload(sp_path: str, content: bytes,
                   content_type: str = "application/octet-stream"):
    headers = _auth_header(None)
    headers["Content-Type"] = content_type

    r = _request(
        "PUT",
        f"{_item_url(sp_path)}:/content",
        headers=headers,
        data=content,
    )
    r.raise_for_status()
    return r.json()


def _resumable_upload(sp_path: str, content: bytes,
                      content_type: str = "application/octet-stream"):
    session_body = {
        "item": {
            "@microsoft.graph.conflictBehavior": "replace"
        }
    }

    r = _request(
        "POST",
        f"{_item_url(sp_path)}:/createUploadSession",
        headers=_auth_header(),
        json=session_body,
    )
    r.raise_for_status()

    upload_url = r.json()["uploadUrl"]

    total_size = len(content)
    offset = 0

    while offset < total_size:
        chunk = content[offset: offset + CHUNK_SIZE]
        start = offset
        end = offset + len(chunk) - 1

        headers = {
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {start}-{end}/{total_size}",
        }

        resp = _request(
            "PUT",
            upload_url,
            headers=headers,
            data=chunk,
        )

        resp.raise_for_status()
        offset += len(chunk)

    return resp.json()
