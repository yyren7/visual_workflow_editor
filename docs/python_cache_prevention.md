# Python 缓存文件防护配置

## 概述

本文档说明如何在项目中防止 Python 生成 `__pycache__` 目录和 `.pyc` 文件。

## 已完成的配置

### 1. 删除现有缓存

- 已删除所有现有的 `__pycache__` 目录
- 已删除所有 `.pyc` 文件

### 2. Git 忽略配置

`.gitignore` 文件已包含以下规则：

```
# Python
__pycache__
*.pyc
```

### 3. DevContainer 环境变量

在 `.devcontainer/devcontainer.json` 中添加了：

```json
"remoteEnv": {
  "PYTHONDONTWRITEBYTECODE": "1"
}
```

### 4. 环境变量示例

在 `example.env` 中添加了注释说明：

```bash
# Python配置
# PYTHONDONTWRITEBYTECODE=1  # 注释：已在 devcontainer.json 中设置，无需重复
```

**注意**: 对于 DevContainer 环境，`PYTHONDONTWRITEBYTECODE` 已在容器级别设置，无需在 `.env` 文件中重复配置。

### 5. Shell 配置

在 `~/.bashrc` 中添加了：

```bash
export PYTHONDONTWRITEBYTECODE=1
```

## 验证

运行以下命令验证配置是否生效：

```bash
python3 -c "import sys; print(f'Python dont_write_bytecode: {sys.dont_write_bytecode}')"
```

输出应该显示 `True`。

## 注意事项

- 设置 `PYTHONDONTWRITEBYTECODE=1` 会稍微增加 Python 的启动时间，因为每次都需要重新编译模块
- 在开发环境中这通常是可接受的，有助于保持代码目录整洁
- 如果需要重新启用缓存，可以将环境变量设置为 `0` 或删除该环境变量

## 配置层级与优先级

### 环境变量设置层级（按优先级排序）:

1. **DevContainer 容器级** (`devcontainer.json` 的 `remoteEnv`) - **最高优先级**
2. **Shell 级** (`~/.bashrc` 中的 export) - **中等优先级**
3. **应用级** (`.env` 文件通过 `load_dotenv()`) - **最低优先级**

### 推荐配置策略:

| 环境类型              | 推荐配置位置          | 原因                           |
| --------------------- | --------------------- | ------------------------------ |
| **DevContainer 开发** | `devcontainer.json`   | 容器级别自动生效，无需重复配置 |
| **本地开发**          | `~/.bashrc` 或 `.env` | 灵活配置，适合不同项目需求     |
| **生产环境**          | 系统环境变量或 `.env` | 便于容器化部署和配置管理       |

## 生效范围

1. **当前会话**: 立即生效 ✓
2. **新终端会话**: 通过 `~/.bashrc` 自动生效 ✓
3. **DevContainer 重建**: 通过 `devcontainer.json` 自动生效 ✓
4. **生产环境**: 可通过系统环境变量或 `.env` 文件配置
