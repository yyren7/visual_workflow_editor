# 数据库表结构报告

**日期:** 2025-03-26 23:56:38  
**数据库URL:** `sqlite:///./flow_editor.db`

## 目录

- [flow_variables](#flow_variables)
- [flows](#flows)
- [json_embeddings](#json_embeddings)
- [users](#users)
- [version_info](#version_info)

## flow_variables

**行数:** 0

### 列

| 名称 | 类型 | 可空 | 默认值 | 自增 |
|------|------|------|--------|------|
| id | INTEGER | 否 |  | 否 |
| flow_id | VARCHAR(36) | 否 |  | 否 |
| key | VARCHAR | 否 |  | 否 |
| value | VARCHAR | 是 |  | 否 |
| created_at | DATETIME | 是 |  | 否 |
| updated_at | DATETIME | 是 |  | 否 |

### 主键

`id`

### 外键

| 本表列 | 引用表 | 引用列 |
|--------|--------|--------|
| flow_id | flows | id |

### 索引

| 名称 | 类型 | 列 |
|------|------|----|
| ix_flow_variables_id | 非唯一 | id |

### 约束

| 名称 | 列 |
|------|----|
| uix_flow_variable | flow_id, key |


## flows

**行数:** 10

### 列

| 名称 | 类型 | 可空 | 默认值 | 自增 |
|------|------|------|--------|------|
| id | VARCHAR(36) | 否 |  | 否 |
| flow_data | JSON | 否 |  | 否 |
| owner_id | VARCHAR(36) | 是 |  | 否 |
| created_at | DATETIME | 是 | CURRENT_TIMESTAMP | 否 |
| updated_at | DATETIME | 是 |  | 否 |
| name | VARCHAR | 否 |  | 否 |

### 主键

`id`

### 外键

| 本表列 | 引用表 | 引用列 |
|--------|--------|--------|
| owner_id | users | id |

### 索引

| 名称 | 类型 | 列 |
|------|------|----|
| ix_flows_id | 非唯一 | id |


## json_embeddings

**行数:** 0

### 列

| 名称 | 类型 | 可空 | 默认值 | 自增 |
|------|------|------|--------|------|
| id | INTEGER | 否 |  | 否 |
| json_data | JSON | 否 |  | 否 |
| embedding_vector | JSON | 否 |  | 否 |
| embedding_metadata | JSON | 是 |  | 否 |
| model_name | VARCHAR | 否 |  | 否 |
| created_at | FLOAT | 否 |  | 否 |
| updated_at | FLOAT | 否 |  | 否 |

### 主键

`id`

### 索引

| 名称 | 类型 | 列 |
|------|------|----|
| ix_json_embeddings_id | 非唯一 | id |


## users

**行数:** 3

### 列

| 名称 | 类型 | 可空 | 默认值 | 自增 |
|------|------|------|--------|------|
| id | VARCHAR(36) | 否 |  | 否 |
| username | VARCHAR | 否 |  | 否 |
| hashed_password | VARCHAR | 否 |  | 否 |
| created_at | DATETIME | 是 | CURRENT_TIMESTAMP | 否 |
| updated_at | DATETIME | 是 |  | 否 |

### 主键

`id`

### 索引

| 名称 | 类型 | 列 |
|------|------|----|
| ix_users_id | 非唯一 | id |
| ix_users_username | 唯一 | username |


## version_info

**行数:** 1

### 列

| 名称 | 类型 | 可空 | 默认值 | 自增 |
|------|------|------|--------|------|
| id | INTEGER | 否 |  | 否 |
| version | VARCHAR | 否 |  | 否 |
| last_updated | VARCHAR | 否 |  | 否 |
| created_at | DATETIME | 是 |  | 否 |
| updated_at | DATETIME | 是 |  | 否 |

### 主键

`id`

### 索引

| 名称 | 类型 | 列 |
|------|------|----|
| ix_version_info_id | 非唯一 | id |


## 关系图

```
flow_variables(flow_id) -> flows(id)
flows(owner_id) -> users(id)
```

---
报告生成完毕
