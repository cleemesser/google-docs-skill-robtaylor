"""Google Docs operations. One method per CLI command."""
from __future__ import annotations

from .auth import build_docs_service
from .markdown import Parsed, build_format_request, parse


class DocsClient:
    def __init__(self, account: str = "default"):
        self._svc = build_docs_service(account)

    # ---- read / structure / create / delete ----

    def read(self, document_id: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        content = _extract_body_text(doc.get("body", {}).get("content", []))
        return {
            "status": "success",
            "operation": "read",
            "document_id": doc.get("documentId"),
            "title": doc.get("title"),
            "content": content,
            "revision_id": doc.get("revisionId"),
        }

    def structure(self, document_id: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        structure = []
        for element in doc.get("body", {}).get("content", []):
            para = element.get("paragraph")
            if not para:
                continue
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            if not style.startswith("HEADING_"):
                continue
            level = int(style.split("_")[-1])
            text = "".join(
                (e.get("textRun") or {}).get("content", "")
                for e in para.get("elements", [])
            )
            structure.append(
                {
                    "level": level,
                    "text": text,
                    "start_index": element.get("startIndex"),
                    "end_index": element.get("endIndex"),
                }
            )
        return {
            "status": "success",
            "operation": "structure",
            "document_id": doc.get("documentId"),
            "title": doc.get("title"),
            "structure": structure,
        }

    def create(self, title: str, content: str | None = None) -> dict:
        doc = self._svc.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        if content:
            self._svc.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {"insertText": {"location": {"index": 1}, "text": content}}
                    ]
                },
            ).execute()
        return {
            "status": "success",
            "operation": "create",
            "document_id": doc_id,
            "title": doc.get("title"),
            "revision_id": doc.get("revisionId"),
        }

    def delete(self, document_id: str, start_index: int, end_index: int) -> dict:
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": start_index, "endIndex": end_index}
                        }
                    }
                ]
            },
        ).execute()
        return {
            "status": "success",
            "operation": "delete",
            "document_id": document_id,
            "deleted_range": {"start": start_index, "end": end_index},
        }

    # ---- text manipulation ----

    def insert(self, document_id: str, text: str, index: int = 1) -> dict:
        result = (
            self._svc.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {"insertText": {"location": {"index": index}, "text": text}}
                    ]
                },
            )
            .execute()
        )
        return {
            "status": "success",
            "operation": "insert",
            "document_id": document_id,
            "inserted_at": index,
            "text_length": len(text),
            "revision_id": result.get("documentId"),
        }

    def append(self, document_id: str, text: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": end_index}, "text": text}}
                ]
            },
        ).execute()
        return {
            "status": "success",
            "operation": "append",
            "document_id": document_id,
            "appended_at": end_index,
            "text_length": len(text),
        }

    def replace(
        self,
        document_id: str,
        find: str,
        replace: str,
        match_case: bool = False,
    ) -> dict:
        result = (
            self._svc.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "replaceAllText": {
                                "containsText": {"text": find, "matchCase": match_case},
                                "replaceText": replace,
                            }
                        }
                    ]
                },
            )
            .execute()
        )
        occurrences = (
            result.get("replies", [{}])[0]
            .get("replaceAllText", {})
            .get("occurrencesChanged", 0)
        )
        return {
            "status": "success",
            "operation": "replace",
            "document_id": document_id,
            "find": find,
            "replace": replace,
            "occurrences": occurrences,
        }

    def format(
        self,
        document_id: str,
        start_index: int,
        end_index: int,
        bold: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
    ) -> dict:
        style: dict = {}
        if bold is not None:
            style["bold"] = bold
        if italic is not None:
            style["italic"] = italic
        if underline is not None:
            style["underline"] = underline
        fields = ",".join(style.keys())
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": end_index,
                            },
                            "textStyle": style,
                            "fields": fields,
                        }
                    }
                ]
            },
        ).execute()
        return {
            "status": "success",
            "operation": "format",
            "document_id": document_id,
            "range": {"start": start_index, "end": end_index},
            "formatting": style,
        }

    def page_break(self, document_id: str, index: int) -> dict:
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {"insertPageBreak": {"location": {"index": index}}}
                ]
            },
        ).execute()
        return {
            "status": "success",
            "operation": "page_break",
            "document_id": document_id,
            "inserted_at": index,
        }

    # ---- images and tables ----

    def insert_image(
        self,
        document_id: str,
        image_url: str,
        index: int | None = None,
        width: float | None = None,
        height: float | None = None,
    ) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        req: dict = {
            "insertInlineImage": {"location": {"index": index}, "uri": image_url}
        }
        obj_size: dict = {}
        if width is not None:
            obj_size["width"] = {"magnitude": width, "unit": "PT"}
        if height is not None:
            obj_size["height"] = {"magnitude": height, "unit": "PT"}
        if obj_size:
            req["insertInlineImage"]["objectSize"] = obj_size
        result = (
            self._svc.documents()
            .batchUpdate(documentId=document_id, body={"requests": [req]})
            .execute()
        )
        return {
            "status": "success",
            "operation": "insert_image",
            "document_id": document_id,
            "inserted_at": index,
            "image_url": image_url,
            "revision_id": result.get("documentId"),
        }

    def insert_table(
        self,
        document_id: str,
        rows: int,
        cols: int,
        index: int | None = None,
        data: list[list[str]] | None = None,
    ) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        self._insert_table_at(document_id, rows, cols, index, data)
        return {
            "status": "success",
            "operation": "insert_table",
            "document_id": document_id,
            "rows": rows,
            "columns": cols,
            "inserted_at": index,
        }

    def _insert_table_at(
        self,
        document_id: str,
        rows: int,
        cols: int,
        index: int,
        data: list[list[str]] | None,
    ) -> None:
        """Insert a table shell, then populate cells from `data` in reverse order
        (to preserve indices). Matches Ruby `insert_table_internal`."""
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {
                        "insertTable": {
                            "rows": rows,
                            "columns": cols,
                            "location": {"index": index},
                        }
                    }
                ]
            },
        ).execute()
        if not data:
            return
        doc = self._svc.documents().get(documentId=document_id).execute()
        table_el = None
        for el in doc["body"].get("content", []):
            if el.get("table") and el.get("startIndex", 0) >= index:
                table_el = el
                break
        if not table_el:
            return
        cell_requests = []
        for row_idx in range(len(data) - 1, -1, -1):
            if row_idx >= rows:
                continue
            row_data = data[row_idx]
            for col_idx in range(len(row_data) - 1, -1, -1):
                if col_idx >= cols:
                    continue
                tr = table_el["table"]["tableRows"][row_idx]
                tc = tr["tableCells"][col_idx]
                cell_start = tc["content"][0]["startIndex"]
                cell_requests.append(
                    {
                        "insertText": {
                            "location": {"index": cell_start},
                            "text": str(row_data[col_idx]),
                        }
                    }
                )
        if cell_requests:
            self._svc.documents().batchUpdate(
                documentId=document_id, body={"requests": cell_requests}
            ).execute()

    # ---- markdown ----

    def create_from_markdown(self, title: str, markdown: str) -> dict:
        doc = self._svc.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        parsed = parse(markdown, base_index=1)
        self._apply_parsed(doc_id, parsed, base_index=1)
        return {
            "status": "success",
            "operation": "create_from_markdown",
            "document_id": doc_id,
            "title": title,
            "revision_id": doc.get("revisionId"),
            "tables_inserted": len(parsed.tables),
        }

    def insert_from_markdown(
        self, document_id: str, markdown: str, index: int | None = None
    ) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        parsed = parse(markdown, base_index=index)
        self._apply_parsed(document_id, parsed, base_index=index)
        return {
            "status": "success",
            "operation": "insert_from_markdown",
            "document_id": document_id,
            "inserted_at": index,
            "text_length": len(parsed.text),
            "formats_applied": len(parsed.formats),
        }

    def _apply_parsed(
        self, document_id: str, parsed: Parsed, base_index: int
    ) -> None:
        # 1. Insert plain text at base_index
        if parsed.text:
            self._svc.documents().batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": base_index},
                                "text": parsed.text,
                            }
                        }
                    ]
                },
            ).execute()
        # 2. Apply formatting in reverse order (preserve indices)
        format_requests = [build_format_request(f) for f in reversed(parsed.formats)]
        if format_requests:
            self._svc.documents().batchUpdate(
                documentId=document_id, body={"requests": format_requests}
            ).execute()
        # 3. Insert tables in reverse order
        for table in reversed(parsed.tables):
            self._insert_table_at(
                document_id,
                table.num_rows,
                table.num_cols,
                table.insert_index,
                table.rows,
            )


def _extract_body_text(elements: list[dict]) -> str:
    parts = []
    for el in elements:
        if "paragraph" in el:
            para = el["paragraph"]
            parts.append(
                "".join(
                    (e.get("textRun") or {}).get("content", "")
                    for e in para.get("elements", [])
                )
            )
        elif "table" in el:
            rows = []
            for row in el["table"].get("tableRows", []):
                cells = [
                    _extract_body_text(cell.get("content", []))
                    for cell in row.get("tableCells", [])
                ]
                rows.append(" | ".join(cells))
            parts.append("\n".join(rows))
    return "\n".join(parts)
