# 后端开发指南

## 数据库迁移

### UUID 迁移

我们将数据库中的 ID 从整数类型更改为 UUID 类型，以提高安全性和系统扩展性。这需要执行以下步骤：

1. 在执行迁移前，请确保已备份数据库：

```bash
pg_dump -U your_username -d your_database > backup_before_migration.sql
```

2. 运行迁移脚本：

```bash
python -m backend.app.migrations.uuid_migration
```

迁移脚本会：

- 将现有表重命名为备份（users -> users_old, flows -> flows_old）
- 创建新的使用 UUID 的表结构
- 将数据从旧表迁移到新表
- 建立正确的关联关系

3. 迁移完成后验证新表数据的完整性
4. 确认无误后，可以删除旧表（迁移脚本中有相关注释代码）
