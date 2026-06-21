# ShuFu Protocol v0.3

## 1. 通用约定

- 传输：HTTP/1.1 或兼容 HTTP；局域网部署；
- 普通响应：`application/json; charset=utf-8`；
- 流响应：`application/x-ndjson; charset=utf-8`；
- 鉴权：可选 `Authorization: Bearer <token>`；
- 时间：UTC ISO-8601；
- 内容哈希：小写十六进制 SHA-256；
- Node 默认仅监听回环地址，LAN 暴露必须显式开启。

## 2. 能力发现

`GET /shufu/v1/capabilities`

兼容路由保留 `protocol_version: "0.2"`，新客户端读取：

```json
{
  "protocol_version": "0.2",
  "latest_protocol_version": "0.3",
  "protocol_versions": ["0.1", "0.2", "0.3"],
  "memory": {
    "bundle_schemas": [1, 2, 3],
    "incremental_sync": true,
    "dual_cursor_sync": true,
    "artifact_transfer": ["inline", "chunks", "external"]
  },
  "invoke": {"streaming": "ndjson"}
}
```

客户端必须基于能力字段协商，不能只比较单个版本字符串。

## 3. 流式调用

`POST /shufu/v3/invoke/stream`

请求：

```json
{
  "model": "assistant",
  "session_id": "device-42",
  "input": "当前温度是多少？",
  "memory_window": 20,
  "stream_chunk_size": 64
}
```

`stream_chunk_size` 范围 1–4096，表示 Node 发送的最大字符块，不是字节块或 token 数。

成功响应示例（每个 JSON 对象单独一行）：

```json
{"type":"start","request_id":"uuid","sequence":0,"protocol_version":"0.3","model":"assistant","session_id":"device-42"}
{"type":"delta","request_id":"uuid","sequence":1,"delta":"当前温度"}
{"type":"delta","request_id":"uuid","sequence":2,"delta":"为 24°C"}
{"type":"done","request_id":"uuid","sequence":3,"created_at":"2026-06-21T08:00:00Z","output_chars":11}
```

若响应头已经发出后运行时失败，Node 发送 `error` 事件而不能更换 HTTP 状态：

```json
{"type":"error","request_id":"uuid","sequence":1,"error":"INVOKE_FAILED","detail":"runtime unavailable"}
```

客户端规则：

1. 首事件必须为 start，sequence 为 0；
2. 后续 request_id 必须一致，sequence 必须连续；
3. delta 按接收顺序拼接；
4. done 后停止；error 视为调用失败；
5. 客户端必须设置单行与总会话资源限制。

## 4. Schema 3 Bundle

顶层：

```json
{
  "schema_version": 3,
  "bundle_id": "uuid",
  "source_node_id": "uuid",
  "exported_at": "2026-06-21T08:00:00Z",
  "after": 10,
  "cursor": 18,
  "sessions": [],
  "messages": [],
  "artifacts": []
}
```

### 4.1 内联产物

```json
{
  "id": "artifact-uuid",
  "session_id": "s",
  "name": "note.md",
  "mime_type": "text/markdown",
  "sha256": "...",
  "size": 12,
  "created_at": "...",
  "content_encoding": "base64",
  "content_base64": "IyBub3Rl"
}
```

### 4.2 分块产物

```json
{
  "id": "artifact-uuid",
  "sha256": "total-sha256",
  "size": 70000,
  "content_encoding": "chunked-base64",
  "chunk_size": 65536,
  "content_chunks": [
    {"index":0,"offset":0,"size":65536,"sha256":"chunk-sha256","content_base64":"..."},
    {"index":1,"offset":65536,"size":4464,"sha256":"chunk-sha256","content_base64":"..."}
  ]
}
```

接收端必须验证连续 index/offset、每块 size/hash、合并后总 size/hash。

### 4.3 外部引用

```json
{
  "id": "artifact-uuid",
  "sha256": "...",
  "size": 70000,
  "content_encoding": "external",
  "content_ref": {
    "url": "/shufu/v3/artifacts/artifact-uuid/content",
    "sha256": "...",
    "size": 70000
  }
}
```

引用是数据而非自动取回指令。客户端必须显式解析，只允许同源 Node，并再次校验哈希和大小。

## 5. 产物字节端点

`GET /shufu/v3/artifacts/{artifact_id}/content`

- 200：完整内容；
- 206：合法单范围 `Range: bytes=start-end`；
- 400：格式错误或多范围；
- 404：产物不存在；
- 416：范围越界。

响应包含 `Content-Length`、`Content-Type`、`Accept-Ranges: bytes` 和 `ETag: "sha256:<digest>"`。

## 6. v3 拉取

`GET /shufu/v3/sync/pull?after=10&session_id=s&artifact_mode=auto`

`artifact_mode` 为 `auto|inline|chunks|external`。响应是 Schema 3 Bundle。cursor 只在该 source_node_id 和 session 范围内解释。

## 7. 双游标交换

`POST /shufu/v3/sync/exchange`

```json
{
  "source_node_id": "client-node-uuid",
  "push_after": 5,
  "pull_after": 8,
  "session_id": null,
  "artifact_mode": "auto",
  "push_bundle": {"schema_version":3,"source_node_id":"client-node-uuid","after":5,"cursor":9}
}
```

Node 校验外层 source_node_id、push_after 与 Bundle 一致。响应：

```json
{
  "protocol_version": "0.3",
  "remote_node_id": "server-node-uuid",
  "acknowledged_push_cursor": 9,
  "imported": {"sessions":1,"messages":2,"artifacts":0},
  "pull_bundle": {"schema_version":3,"after":8,"cursor":12}
}
```

持久化规则：

- 收到成功响应后，用 acknowledged_push_cursor 单调推进 pushed cursor；
- 成功导入并校验 pull_bundle 后，才用其 cursor 推进 pulled cursor；
- 网络失败、JSON 失败、哈希失败不得推进对应游标；
- 为目标远端导出时，排除 `origin_node_id` 等于该远端的对象。

## 8. 兼容端点

| 端点 | v0.3 行为 |
| --- | --- |
| `POST /shufu/v1/invoke` | 原 JSON 请求/响应不变 |
| `GET /shufu/v1/memory/export` | 强制 Schema 1 |
| `POST /shufu/v1/memory/import` | 接受 Schema 1/2/3 |
| `GET /shufu/v2/sync/pull` | 强制 Schema 2 + 内联产物 |
| `POST /shufu/v2/sync/push` | 兼容 Schema 2 幂等导入 |
| `GET/POST /shufu/v1/artifacts` | 原 Base64 行为不变 |

## 9. 错误模型

普通 JSON 端点使用：

```json
{"error":"INVALID_REQUEST","detail":"..."}
```

主要状态码：400 无效请求、401 Token 缺失/错误、404 未找到、416 范围错误。客户端不自动重试 invoke 或工具副作用；同步重试依靠不可变 ID、哈希与游标幂等。
