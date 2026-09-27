"""WSGI entry point for public deployment."""

import json
import re
from datetime import datetime

from server import ExpressionError, calculate, connect_database, initialize_database


def response(start_response, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ])
    return [body]


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "OPTIONS":
        return response(start_response, "204 No Content", {})

    if method == "POST" and path == "/api/calculate":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            data = json.loads(environ["wsgi.input"].read(length))
            expression = data.get("expression")
            result = calculate(expression)
            created_at = datetime.now().astimezone().isoformat(timespec="seconds")
            with connect_database() as connection:
                cursor = connection.execute(
                    "INSERT INTO history (expression, result, created_at) VALUES (?, ?, ?)",
                    (expression, str(result), created_at),
                )
                record_id = cursor.lastrowid
            return response(start_response, "201 Created", {
                "success": True, "id": record_id, "expression": expression,
                "result": result, "created_at": created_at,
            })
        except (ExpressionError, json.JSONDecodeError, AttributeError) as error:
            return response(start_response, "400 Bad Request", {
                "success": False, "message": str(error) or "请求格式错误",
            })
        except Exception:
            return response(start_response, "500 Internal Server Error", {
                "success": False, "message": "服务器内部错误",
            })

    if method == "GET" and path == "/api/history":
        with connect_database() as connection:
            rows = connection.execute(
                "SELECT id, expression, result, created_at FROM history ORDER BY id DESC"
            ).fetchall()
        return response(start_response, "200 OK", {
            "success": True, "history": [dict(row) for row in rows],
        })

    match = re.fullmatch(r"/api/history/(\d+)", path)
    if method == "DELETE" and match:
        with connect_database() as connection:
            cursor = connection.execute(
                "DELETE FROM history WHERE id = ?", (int(match.group(1)),)
            )
        if cursor.rowcount == 0:
            return response(start_response, "404 Not Found", {
                "success": False, "message": "历史记录不存在",
            })
        return response(start_response, "200 OK", {
            "success": True, "message": "删除成功",
        })

    return response(start_response, "404 Not Found", {
        "success": False, "message": "接口不存在",
    })


initialize_database()


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    print("Calculator API: http://127.0.0.1:8000")
    make_server("127.0.0.1", 8000, application).serve_forever()
