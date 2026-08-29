# 协作指南

## 开发流程

1. 从 `main` 创建功能分支，例如 `feat/map-cards` 或 `fix/dify-dsl`。
2. 不要提交任何 `.env*` 文件、API Key、访问令牌或真实用户定位数据。
3. 修改后运行：

   ```bash
   cd backend
   pip install -r requirements-dev.txt
   pytest -q
   node --check ../frontend/app.js
   ```

4. 提交 Pull Request，说明改动、测试方式以及是否涉及 Dify DSL。
5. Dify Cloud 中完成的画布修改，应重新导出 DSL，并与 `dify/campus-life-chatflow.yml` 比较后提交。

## 提交约定

推荐使用以下前缀：

- `feat:` 新功能
- `fix:` 缺陷修复
- `docs:` 文档
- `test:` 测试
- `chore:` 工程维护

## Dify DSL 注意事项

- 当前 DSL 版本为 `0.6.0`。
- `environment_variables` 必须保持为空数组；变量和值只在 Dify Cloud 中手工配置。
- Code 节点输入必须使用 `value_selector`，不能使用旧的 `value` 字段。
- 禁止将环境变量真实值或模型凭据导出到仓库。
- 提交前运行 `backend/tests/test_dify_dsl.py`。
