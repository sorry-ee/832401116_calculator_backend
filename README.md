# Calculator Backend

作者：林昊旻（学号：832401116）

前后端分离计算器的后端 API。使用 Python 标准库实现表达式解析、HTTP 服务和 SQLite 持久化，无第三方依赖，也没有使用 `eval` 或 `exec`。

## 技术栈与环境

- Python 3.10+
- `http.server`：HTTP API
- `sqlite3`：计算历史持久化
- 递归下降解析器：安全解析数学表达式

## 启动

```bash
python3 server.py
```

服务地址为 `http://127.0.0.1:8000`。首次启动会自动创建 `calculator.db` 和 `history` 表，不需要手工初始化。

## 测试

```bash
python3 -m unittest -v
```

## API

- `POST /api/calculate`：请求体 `{"expression":"(1+2)*3"}`
- `GET /api/history`：查询全部历史
- `DELETE /api/history/{id}`：删除指定记录

所有响应均为 JSON。前端默认连接 `http://127.0.0.1:8000`，部署后需将前端 `index.html` 中的 `API_BASE` 攓为公网后端地址。

## 数据库结构

`history(id, expression, result, created_at)`。每次成功计算立即写入 SQLite，非法表达式不会保存。
