# LMStudio Embedding 设置指南

本文档介绍如何设置 LMStudio 来为 Visual Workflow Editor 提供嵌入(Embedding)计算服务。项目已经精简，**仅支持通过 LMStudio API 进行 embedding 计算**，不再支持本地 embedding 模型。

## 1. 安装 LMStudio

1. 访问[LMStudio 官方网站](https://lmstudio.ai/)下载并安装 LMStudio。
2. 启动 LMStudio 应用程序。

## 2. 选择 Embedding 模型

在 LMStudio 中，您需要选择一个适合生成文本嵌入的模型：

1. 在 LMStudio 界面中，点击"模型"或"Models"选项卡。
2. 搜索并下载一个支持嵌入的模型。推荐以下模型：

   - `BAAI/bge-small-en` (英文小型模型)
   - `BAAI/bge-small-zh` (中文小型模型)
   - `BAAI/bge-m3` (多语言支持)
   - `intfloat/multilingual-e5-base` (多语言支持)

3. 下载完成后，在模型列表中选择该模型，然后点击"加载模型"或"Load Model"。

## 3. 启动 OpenAI 兼容 API 服务器

LMStudio 可以启动一个兼容 OpenAI API 格式的服务器，我们将使用这个功能：

1. 在 LMStudio 界面中，点击右上角的"服务器"或"Server"按钮。
2. 在弹出的对话框中，确保选择了"嵌入模型"或"Embedding Model"选项。
3. 设置以下参数：

   - 主机(Host): `0.0.0.0`（允许远程访问）或 `127.0.0.1`（仅本地访问）
   - 端口(Port): `1234`（或其他未被占用的端口）
   - API 密钥(API Key): 可选设置，如果设置了，需要在配置中提供相同的密钥

4. 点击"启动服务器"或"Start Server"。

## 4. 配置 Visual Workflow Editor

启动 LMStudio API 服务器后，需要配置项目使用这个服务：

1. 在项目根目录创建或修改`.env`文件（可以复制`example.env`）。
2. 设置以下环境变量：

   ```
   EMBEDDING_USE_LMSTUDIO=True
   EMBEDDING_LMSTUDIO_API_BASE_URL=http://localhost:1234/v1
   EMBEDDING_LMSTUDIO_API_KEY=your_api_key_if_set
   ```

   如果 LMStudio 在不同机器上运行，请相应修改 URL 中的主机名。

## 5. 测试嵌入功能

配置完成后，您可以测试嵌入功能：

1. 重启后端服务。
2. 通过 API 创建一个新的嵌入或使用前端的相关功能。
3. 检查日志以确认嵌入计算是否成功。

## 6. 故障排除

- **连接错误**：确保 LMStudio 服务器正在运行，并且配置的 URL 和端口正确。
- **认证错误**：如果设置了 API 密钥，确保在环境变量中提供了相同的密钥。
- **嵌入计算失败**：检查选择的模型是否支持嵌入计算。某些语言模型不支持嵌入功能。
- **不启用 LMStudio**：如果不设置`EMBEDDING_USE_LMSTUDIO=True`，系统将回退到使用简单的关键词匹配算法，而不是真正的 embedding 技术。

## 7. 注意事项

- LMStudio 可能消耗大量计算资源，特别是 GPU 资源。确保您的系统有足够的资源运行选择的模型。
- 嵌入向量的维度可能因模型而异。如果更改模型，可能需要调整`VECTOR_DIMENSION`配置。
- 如果使用大型模型，第一次嵌入计算可能需要较长时间，因为模型需要加载到内存中。

## 8. 性能优化

- 对于批量嵌入计算，使用批处理 API 可以提高性能。
- 在生产环境中，考虑使用专用的嵌入服务或优化过的模型以提高性能。
- 定期清理不必要的嵌入数据以优化数据库性能。
