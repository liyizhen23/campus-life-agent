# Dify Cloud 配置

## 1. 配置 DeepSeek

1. 登录 Dify Cloud，进入 **Plugins / 插件市场**。
2. 安装官方/受信任的 **DeepSeek Model Provider**。
3. 在 **Settings → Model Provider → DeepSeek** 中填写 DeepSeek API Key。
4. 优先选择 `deepseek-v4-flash`。本场景主要是参数提取和简短说明，不需要默认使用成本更高的 Pro。

> DeepSeek 已在 2026 年将旧的 `deepseek-chat` / `deepseek-reasoner` 名称下线。本项目 DSL 使用当前的 `deepseek-v4-flash`。如果 Dify 插件的模型列表尚未刷新，请在导入后直接在两个模型节点中选择插件实际展示的最新 Flash 模型。

## 2. 导入 Chatflow

在 Dify Studio 选择 **Import DSL file**，导入 `dify/campus-life-chatflow.yml`。

DSL 已按当前 Dify `0.6.0` 导出结构整理。导入后检查以下五个节点：

1. 开始
2. 提取推荐条件
3. 标准化请求
4. 高德附近推荐
5. 生成推荐说明 → 回复

如果 DeepSeek 模型节点显示未配置，分别重新选择 `deepseek-v4-flash`。

## 3. 配置 Chatflow 环境变量

DSL 文件故意不携带环境变量定义或值。导入完成后，在 Dify Cloud 的 Chatflow 环境变量面板中手工新建并填写：

- `BACKEND_BASE_URL`：本项目部署后的公网 HTTPS 地址，不要以 `/` 结尾。
- `INTERNAL_API_TOKEN`：与服务器 `.env` 中同名变量完全一致。

不得将填写后的 DSL 再导出并直接提交到 GitHub；提交前必须确认 `environment_variables: []`。

Dify Cloud 无法访问 `localhost`，因此测试“高德附近推荐”节点前，后端必须先部署到公网 HTTPS 地址。

## 4. 发布并取得应用 Key

1. 点击 **Publish**。
2. 打开 **Access API / 访问 API**。
3. 创建应用 API Key。
4. 把 Key 填入服务器 `.env` 的 `DIFY_API_KEY`，不要写进 H5 JavaScript。

H5 经后端调用：

```text
POST https://api.dify.ai/v1/chat-messages
```

输入变量由后端自动传递：`longitude`、`latitude`、`coordinate_system`、`location_accuracy` 和 `fallback_location_name`。

## 5. 联调

依次验证：

1. `GET /api/health` 三项配置均为 `true`。
2. 在 Dify 调试页手动填清华默认坐标 `116.3260, 40.0030`，运行 Chatflow。
3. 打开 H5，允许定位，询问“推荐附近人均 60 的晚餐”。
4. 拒绝定位再次测试，应回退到清华大学默认位置。
5. 点击答案中的“打开高德导航”。

生产前请为 `/api/chat` 增加网关限流，并把高德/Dify 调用日志接入监控。
