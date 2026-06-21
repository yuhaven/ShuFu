# ShuFu Protocol v0.1

Base URL：`http://127.0.0.1:7878`

## GET /health

返回节点存活状态。

## GET /shufu/v1/capabilities

返回协议版本、runtime、记忆和 Agent 扩展能力。

## POST /shufu/v1/invoke

请求：

```json
{
  "model": "assistant",
  "session_id": "project-a",
  "input": "继续完善文档",
  "memory_window": 20
}
```

响应：

```json
{
  "session_id": "project-a",
  "model": "assistant",
  "output": "...",
  "created_at": "2026-06-19T10:00:00Z"
}
```

## GET /shufu/v1/memory/export?session_id=project-a

导出 `schema_version=1` 的可移植记忆包。

## POST /shufu/v1/memory/import

请求体直接使用导出的 Bundle。重复导入通过 ID 和哈希去重。

## POST /shufu/v1/artifacts

```json
{
  "session_id": "project-a",
  "name": "notes.md",
  "mime_type": "text/markdown",
  "content_base64": "IyBOb3Rlcw=="
}
```

## GET /shufu/v1/artifacts/{artifact_id}

返回产物元数据和 Base64 内容。

## 鉴权

默认无鉴权且只监听回环地址。配置 token 后使用：

```text
Authorization: Bearer <token>
```

## 兼容性

所有可持久化对象包含稳定 ID，Bundle 包含 `schema_version`。v0.1 客户端必须忽略未知字段。

