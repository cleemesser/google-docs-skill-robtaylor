"""Google Drive operations. One method per CLI command.

Uses --flag-style CLI args (unlike docs_manager which uses JSON stdin).
"""
from __future__ import annotations

import mimetypes
import os

from googleapiclient.http import MediaFileUpload

from .auth import build_drive_service

_EXT_MIME = {
    ".excalidraw": "application/json",
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".zip": "application/zip",
    ".csv": "text/csv",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
}

_EXPORT_DEFAULT = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "image/png",
}


def detect_mime_type(file_path: str) -> str:
    _, ext = os.path.splitext(file_path.lower())
    return (
        _EXT_MIME.get(ext)
        or mimetypes.guess_type(file_path)[0]
        or "application/octet-stream"
    )


def _file_dict(f: dict) -> dict:
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "mime_type": f.get("mimeType"),
        "web_view_link": f.get("webViewLink"),
        "web_content_link": f.get("webContentLink"),
        "parents": f.get("parents"),
        "created_time": f.get("createdTime"),
        "modified_time": f.get("modifiedTime"),
        "size": f.get("size"),
    }


class DriveClient:
    FIELDS_BASIC = (
        "id, name, mimeType, webViewLink, webContentLink, parents, "
        "createdTime, modifiedTime, size"
    )

    def __init__(self, account: str = "default"):
        self._svc = build_drive_service(account)

    def upload(
        self,
        file: str,
        name: str | None = None,
        folder_id: str | None = None,
        mime_type: str | None = None,
    ) -> dict:
        if not os.path.exists(file):
            return {
                "status": "error",
                "error_code": "FILE_NOT_FOUND",
                "operation": "upload",
                "message": f"File not found: {file}",
            }
        mt = mime_type or detect_mime_type(file)
        metadata: dict = {"name": name or os.path.basename(file)}
        if folder_id:
            metadata["parents"] = [folder_id]
        media = MediaFileUpload(file, mimetype=mt, resumable=False)
        created = (
            self._svc.files()
            .create(body=metadata, media_body=media, fields=self.FIELDS_BASIC)
            .execute()
        )
        return {"status": "success", "operation": "upload", "file": _file_dict(created)}

    def download(
        self, file_id: str, output: str, export_as: str | None = None
    ) -> dict:
        meta = (
            self._svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
        )
        if meta["mimeType"].startswith("application/vnd.google-apps."):
            export_mime = export_as or _EXPORT_DEFAULT.get(
                meta["mimeType"], "application/pdf"
            )
            data = (
                self._svc.files()
                .export(fileId=file_id, mimeType=export_mime)
                .execute()
            )
            with open(output, "wb") as fh:
                fh.write(data)
            return {
                "status": "success",
                "operation": "export",
                "file_id": file_id,
                "output_path": output,
                "export_mime_type": export_mime,
            }
        request = self._svc.files().get_media(fileId=file_id)
        with open(output, "wb") as fh:
            fh.write(request.execute())
        return {
            "status": "success",
            "operation": "download",
            "file_id": file_id,
            "output_path": output,
            "name": meta["name"],
            "mime_type": meta["mimeType"],
        }

    def list_files(
        self, folder_id: str | None = None, max_results: int = 100
    ) -> dict:
        query = ["trashed = false"]
        if folder_id:
            query.append(f"'{folder_id}' in parents")
        results = (
            self._svc.files()
            .list(
                q=" and ".join(query),
                pageSize=max_results,
                fields=f"nextPageToken, files({self.FIELDS_BASIC})",
            )
            .execute()
        )
        files = [_file_dict(f) for f in results.get("files", [])]
        return {
            "status": "success",
            "operation": "list",
            "folder_id": folder_id,
            "files": files,
            "next_page_token": results.get("nextPageToken"),
            "count": len(files),
        }

    def search(self, query: str, max_results: int = 100) -> dict:
        full_query = query if "trashed" in query else f"{query} and trashed = false"
        results = (
            self._svc.files()
            .list(
                q=full_query,
                pageSize=max_results,
                fields=f"nextPageToken, files({self.FIELDS_BASIC})",
            )
            .execute()
        )
        files = [_file_dict(f) for f in results.get("files", [])]
        return {
            "status": "success",
            "operation": "search",
            "query": query,
            "files": files,
            "next_page_token": results.get("nextPageToken"),
            "count": len(files),
        }

    def get_metadata(self, file_id: str) -> dict:
        fields = (
            "id, name, mimeType, webViewLink, webContentLink, parents, "
            "createdTime, modifiedTime, size, description, starred, trashed, "
            "owners, permissions"
        )
        f = self._svc.files().get(fileId=file_id, fields=fields).execute()
        return {
            "status": "success",
            "operation": "get_metadata",
            "file": {
                **_file_dict(f),
                "description": f.get("description"),
                "starred": f.get("starred"),
                "trashed": f.get("trashed"),
                "owners": [
                    {"email": o.get("emailAddress"), "name": o.get("displayName")}
                    for o in (f.get("owners") or [])
                ],
                "permissions": [
                    {
                        "id": p.get("id"),
                        "type": p.get("type"),
                        "role": p.get("role"),
                        "email": p.get("emailAddress"),
                    }
                    for p in (f.get("permissions") or [])
                ],
            },
        }

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        metadata: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]
        result = (
            self._svc.files()
            .create(
                body=metadata,
                fields="id, name, mimeType, webViewLink, parents, createdTime",
            )
            .execute()
        )
        return {
            "status": "success",
            "operation": "create_folder",
            "folder": {
                "id": result["id"],
                "name": result["name"],
                "web_view_link": result.get("webViewLink"),
                "parents": result.get("parents"),
                "created_time": result.get("createdTime"),
            },
        }

    def move(self, file_id: str, folder_id: str) -> dict:
        f = self._svc.files().get(fileId=file_id, fields="parents").execute()
        previous = ",".join(f.get("parents") or [])
        result = (
            self._svc.files()
            .update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous,
                body={},
                fields="id, name, parents, webViewLink",
            )
            .execute()
        )
        return {
            "status": "success",
            "operation": "move",
            "file": {
                "id": result["id"],
                "name": result["name"],
                "parents": result.get("parents"),
                "web_view_link": result.get("webViewLink"),
            },
        }

    def share(
        self,
        file_id: str,
        email: str | None = None,
        role: str = "reader",
        type: str | None = None,
        domain: str | None = None,
    ) -> dict:
        perm_type = type or ("user" if email else "anyone")
        body: dict = {"type": perm_type, "role": role}
        if email and perm_type == "user":
            body["emailAddress"] = email
        if domain and perm_type == "domain":
            body["domain"] = domain
        permission = (
            self._svc.permissions()
            .create(fileId=file_id, body=body, fields="id, type, role, emailAddress")
            .execute()
        )
        info = (
            self._svc.files()
            .get(fileId=file_id, fields="webViewLink, webContentLink")
            .execute()
        )
        return {
            "status": "success",
            "operation": "share",
            "permission": {
                "id": permission["id"],
                "type": permission["type"],
                "role": permission["role"],
                "email": permission.get("emailAddress"),
            },
            "web_view_link": info.get("webViewLink"),
            "web_content_link": info.get("webContentLink"),
        }

    def delete(self, file_id: str, permanent: bool = False) -> dict:
        if permanent:
            self._svc.files().delete(fileId=file_id).execute()
        else:
            self._svc.files().update(fileId=file_id, body={"trashed": True}).execute()
        return {
            "status": "success",
            "operation": "delete",
            "file_id": file_id,
            "permanent": permanent,
        }

    def copy(
        self,
        file_id: str,
        name: str | None = None,
        folder_id: str | None = None,
    ) -> dict:
        body: dict = {}
        if name:
            body["name"] = name
        if folder_id:
            body["parents"] = [folder_id]
        result = (
            self._svc.files()
            .copy(
                fileId=file_id,
                body=body,
                fields="id, name, mimeType, webViewLink, parents, createdTime",
            )
            .execute()
        )
        return {
            "status": "success",
            "operation": "copy",
            "file": {
                "id": result["id"],
                "name": result["name"],
                "mime_type": result.get("mimeType"),
                "web_view_link": result.get("webViewLink"),
                "parents": result.get("parents"),
                "created_time": result.get("createdTime"),
            },
        }

    def update(self, file_id: str, file: str, name: str | None = None) -> dict:
        if not os.path.exists(file):
            return {
                "status": "error",
                "error_code": "FILE_NOT_FOUND",
                "operation": "update",
                "message": f"File not found: {file}",
            }
        mt = detect_mime_type(file)
        body: dict = {}
        if name:
            body["name"] = name
        media = MediaFileUpload(file, mimetype=mt, resumable=False)
        result = (
            self._svc.files()
            .update(
                fileId=file_id,
                media_body=media,
                body=body,
                fields="id, name, mimeType, webViewLink, modifiedTime, size",
            )
            .execute()
        )
        return {
            "status": "success",
            "operation": "update",
            "file": {
                "id": result["id"],
                "name": result["name"],
                "mime_type": result.get("mimeType"),
                "web_view_link": result.get("webViewLink"),
                "modified_time": result.get("modifiedTime"),
                "size": result.get("size"),
            },
        }
