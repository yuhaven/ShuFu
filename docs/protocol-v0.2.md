# ShuFu Protocol v0.2

v0.2 是 v0.1 的兼容扩展。调用仍使用 `/shufu/v1/invoke`，新增发现与同步协议。

## 1. 能力

`GET /shufu/v1/capabilities`

```json
{
  "protocol_version": "0.2",
  "protocol_versions": ["0.1", "0.2"],
  "node_id": "...",
  "memory": {
    "bundle_schemas": [1, 2],
    "incremental_sync": true
  },
  "discovery": {
    "method": "udp-broadcast",
    "port": 7879
  }
}
```

## 2. UDP 发现

客户端向局域网 UDP 7879 广播 UTF-8 字节：

```text
SHUFU_DISCOVER_V2
```

节点单播回复：

```json
{
  "service": "shufu",
  "node_id": "stable-uuid",
  "name": "Desktop",
  "url": "http://192.168.1.20:7878",
  "protocol_version": "0.2"
}
```

发现结果只是候选地址，不自动授予权限。

## 3. Bundle Schema 2

```json
{
  "schema_version": 2,
  "bundle_id": "uuid",
  "source_node_id": "uuid",
  "after": 10,
  "cursor": 18,
  "exported_at": "2026-06-19T00:00:00Z",
  "sessions": [],
  "messages": [],
  "artifacts": []
}
```

`cursor` 只对产生它的 `source_node_id` 有意义。客户端不得把一个节点的 cursor 用于另一个节点。

## 4. 增量拉取

```text
GET /shufu/v2/sync/pull?after=18&session_id=project-a
```

首次同步使用 `after=0`。服务端返回新的 cursor。

## 5. 幂等推送

```text
POST /shufu/v2/sync/push
Content-Type: application/json

<Bundle Schema 2>
```

响应：

```json
{
  "sessions": 1,
  "messages": 4,
  "artifacts": 1,
  "cursor": 27
}
```

计数只包含新插入对象。已有 ID 不覆盖、不重复计数。

## 6. 兼容性

- v0.1 调用端点不变；
- `/shufu/v1/memory/export` 始终返回 Schema 1；
- v0.2 导入器接受 Schema 1 和 Schema 2；
- 客户端必须忽略未知字段。

