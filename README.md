# 附近发现 · NearbyGo

基于用户当前实时位置的 H5 吃喝玩乐推荐助手。H5 在获得用户授权后获取当前位置，后端将坐标和问题发送到 Dify Cloud Chatflow；Chatflow 调用本服务封装的高德 POI 与路径规划接口，再由 DeepSeek 生成有依据的附近推荐。

推荐范围不绑定城市或固定地点，而是始终以用户本次定位为中心，并结合预算、距离、出行方式和个人偏好筛选餐饮、咖啡、娱乐、购物、景点等场所。

## 已包含

- 移动端 H5 聊天页面
- 浏览器实时定位与定位授权状态提示
- Dify Cloud SSE 流式聊天代理，避免前端泄露 Dify Key
- Dify reasoning 双层过滤，只向页面展示最终答案
- 浏览器本地保存最近 12 轮对话，可随时清空且不保存定位
- GPS → 高德坐标转换
- 高德周边 POI 搜索
- Top 候选步行/驾车路线计算
- 预算、距离、偏好和评分的确定性排序
- 高德一键导航链接
- Dify Chatflow DSL 和配置文档

## 所需凭据

真实 Key 和本地 `.env` 文件不得提交到 Git。仓库中的 `.env.example` 只提供变量名和非敏感默认值；请使用 Dify、部署平台或服务器的 Secret 管理功能保存真实凭据：

1. Dify Cloud Chatflow 应用 API Key
2. 高德开放平台 **Web 服务 API Key**
3. DeepSeek API Key（只配置在 Dify Cloud 模型供应商中）
4. 自行生成的 `INTERNAL_API_TOKEN`

当前 H5 不展示地图，使用浏览器原生定位，因此第一版不需要高德 JS API Key/安全密钥。将来加入地图组件时再申请。

## 本地启动

```bash
# 每位开发者首次运行时复制模板，并在 .env 中填写自己的真实凭据。
cp .env.example .env
docker compose up --build
```

Docker Compose 会自动读取仓库根目录的 `.env`。至少填写 `DIFY_API_KEY`、`AMAP_WEB_SERVICE_KEY` 和 `INTERNAL_API_TOKEN`；其中 `INTERNAL_API_TOKEN` 必须与 Dify Chatflow 中的同名变量一致。`.env` 已被 Git 忽略，不得强制提交。

打开 `http://localhost:8000`。浏览器精确定位在生产环境需要 HTTPS；localhost 通常可用于本地开发。

不使用 Docker：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

## Dify 配置

按照 [dify/SETUP.md](dify/SETUP.md) 导入 DSL、配置 DeepSeek，并在 Dify Cloud 中检查两个 Chatflow 环境变量。DSL 包含公开后端地址和空的 Token 占位符，不包含真实秘密值。

## 关键接口

- `GET /api/health`：配置状态
- `POST /api/chat`：H5 调用的 Dify SSE 代理
- `POST /api/recommendations`：Dify HTTP 节点调用的高德推荐接口，需要 `X-Internal-Token`

推荐接口示例：

```json
{
  "longitude": 121.4737,
  "latitude": 31.2304,
  "coordinate_system": "gps",
  "categories": ["美食"],
  "keywords": ["川菜"],
  "preferences": ["辣"],
  "budget_per_person": 80,
  "radius_meters": 3000,
  "transport": "walking",
  "result_count": 3
}
```

## 安全边界

- Dify Key、高德 Web 服务 Key、DeepSeek Key 均不进入浏览器。
- POI 返回文本被视为不可信数据，最终提示词禁止依据其内容改变系统规则。
- 定位不写数据库；当前只随单次聊天请求转发。
- 上线前应补充用户同意说明、请求限流、日志脱敏和 Key 轮换。
