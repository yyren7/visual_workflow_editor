# 后端开发指南

## 环境设置

### API 密钥配置

为了保证安全，API 密钥应通过环境变量提供，不应在代码中明文保存。系统支持以下几种方式设置 API 密钥（按优先级排序）：

1. **环境变量方式**（推荐，临时有效）：

```bash
export DEEPSEEK_API_KEY=your_actual_key_here
```

2. **.env 文件方式**（本地开发推荐）：

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑.env文件
nano .env
# 添加: DEEPSEEK_API_KEY=your_actual_key_here
```

3. **.bashrc 方式**（长期有效）：

```bash
# 编辑.bashrc文件
nano ~/.bashrc

# 在文件末尾添加
export DEEPSEEK_API_KEY='your_actual_key_here'

# 使更改生效
source ~/.bashrc
```

系统启动时会自动尝试以上三种方式读取 API 密钥。

### 启动后端服务

确保环境变量设置完成后，启动后端服务：

```bash
python run_backend.py
```

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
