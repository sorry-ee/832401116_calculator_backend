"""Calculator API using only Python's standard library."""

import json
import math
import re
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


DATABASE = Path(__file__).with_name("calculator.db")
TOKEN_RE = re.compile(r"\s*(sqrt|\d+(?:\.\d*)?|\.\d+|[+\-*/^()%])")


class ExpressionError(ValueError):
    """Raised when the expression is invalid."""


class Parser:
    def __init__(self, expression):
        if not isinstance(expression, str) or not expression.strip():
            raise ExpressionError("表达式不能为空")
        if len(expression) > 200:
            raise ExpressionError("表达式过长")
        self.tokens = self._tokenize(expression)
        self.position = 0

    @staticmethod
    def _tokenize(expression):
        tokens = []
        position = 0
        while position < len(expression):
            match = TOKEN_RE.match(expression, position)
            if not match:
                raise ExpressionError("表达式包含非法字符")
            tokens.append(match.group(1))
            position = match.end()
        return tokens

    def parse(self):
        result = self._expression()
        if self.position != len(self.tokens):
            raise ExpressionError("表达式格式错误")
        if not math.isfinite(result):
            raise ExpressionError("结果超出范围")
        return result

    def _expression(self):
        value = self._term()
        while self._peek() in ("+", "-"):
            operator = self._take()
            right = self._term()
            value = value + right if operator == "+" else value - right
        return value

    def _term(self):
        value = self._unary()
        while self._peek() in ("*", "/"):
            operator = self._take()
            right = self._unary()
            if operator == "/" and right == 0:
                raise ExpressionError("除数不能为零")
            value = value * right if operator == "*" else value / right
        return value

    def _unary(self):
        if self._peek() in ("+", "-"):
            operator = self._take()
            value = self._unary()
            return value if operator == "+" else -value
        return self._power()

    def _power(self):
        value = self._primary()
        if self._peek() == "^":
            self._take()
            exponent = self._unary()
            try:
                value = value**exponent
            except (OverflowError, ValueError, ZeroDivisionError):
                raise ExpressionError("次方运算无效") from None
            if isinstance(value, complex):
                raise ExpressionError("暂不支持复数结果")
        return value

    def _primary(self):
        token = self._peek()
        if token == "sqrt":
            self._take()
            self._expect("(")
            value = self._expression()
            self._expect(")")
            if value < 0:
                raise ExpressionError("负数不能开平方根")
            value = math.sqrt(value)
        elif token == "(":
            self._take()
            value = self._expression()
            self._expect(")")
        elif token and re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", token):
            value = float(self._take())
        else:
            raise ExpressionError("表达式格式错误")

        while self._peek() == "%":
            self._take()
            value /= 100
        return value

    def _peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def _take(self):
        token = self._peek()
        self.position += 1
        return token

    def _expect(self, expected):
        if self._take() != expected:
            raise ExpressionError("括号不匹配")


def calculate(expression):
    value = Parser(expression).parse()
    rounded = round(value, 12)
    return int(rounded) if rounded.is_integer() else rounded


def connect_database():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with connect_database() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


class CalculatorHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_POST(self):
        if urlparse(self.path).path != "/api/calculate":
            self._send_json(404, {"success": False, "message": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            expression = data.get("expression")
            result = calculate(expression)
            created_at = datetime.now().astimezone().isoformat(timespec="seconds")
            with connect_database() as connection:
                cursor = connection.execute(
                    "INSERT INTO history (expression, result, created_at) VALUES (?, ?, ?)",
                    (expression, str(result), created_at),
                )
                record_id = cursor.lastrowid
            self._send_json(201, {
                "success": True,
                "id": record_id,
                "expression": expression,
                "result": result,
                "created_at": created_at,
            })
        except (ExpressionError, json.JSONDecodeError, AttributeError) as error:
            self._send_json(400, {"success": False, "message": str(error) or "请求格式错误"})
        except Exception:
            self._send_json(500, {"success": False, "message": "服务器内部错误"})

    def do_GET(self):
        if urlparse(self.path).path != "/api/history":
            self._send_json(404, {"success": False, "message": "接口不存在"})
            return
        with connect_database() as connection:
            rows = connection.execute(
                "SELECT id, expression, result, created_at FROM history ORDER BY id DESC"
            ).fetchall()
        self._send_json(200, {"success": True, "history": [dict(row) for row in rows]})

    def do_DELETE(self):
        match = re.fullmatch(r"/api/history/(\d+)", urlparse(self.path).path)
        if not match:
            self._send_json(404, {"success": False, "message": "接口不存在"})
            return
        with connect_database() as connection:
            cursor = connection.execute("DELETE FROM history WHERE id = ?", (int(match.group(1)),))
        if cursor.rowcount == 0:
            self._send_json(404, {"success": False, "message": "历史记录不存在"})
            return
        self._send_json(200, {"success": True, "message": "删除成功"})

    def log_message(self, message_format, *args):
        print(f"[{self.log_date_time_string()}] {message_format % args}")


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), CalculatorHandler)
    print("Calculator API: http://127.0.0.1:8000")
    server.serve_forever()
