---
name: ones-plugin
description: ONES OP Plugin（Settings-only）通用交付指引，兼容 Codex 与 OpenClaw。
---

# ONES OP Plugin Skill (Codex + OpenClaw)

本技能用于在 ONES 上开发、调试、打包、升级 Settings-only 插件，要求流程可同时被 Codex 和 OpenClaw 执行。

## 1. 适用范围
- 插件类型：优先 `settings` 模块。
- 目标：稳定交付可安装 `.opk`，并在目标环境通过最小回归。
- 兼容：不依赖平台专属 UI；以 shell 命令 + 可验证证据为主。

## 2. 开发前必读（按顺序）
1. 安装环境说明  
- [https://developer.ones.cn/zh-CN/docs/guide/getting-started/install](https://developer.ones.cn/zh-CN/docs/guide/getting-started/install)
2. 创建插件  
- [https://developer.ones.cn/zh-CN/docs/guide/getting-started/create](https://developer.ones.cn/zh-CN/docs/guide/getting-started/create)
3. 开发插件  
- [https://developer.ones.cn/zh-CN/docs/guide/getting-started/development](https://developer.ones.cn/zh-CN/docs/guide/getting-started/development)
4. 插件打包  
- [https://developer.ones.cn/zh-CN/docs/guide/getting-started/packup](https://developer.ones.cn/zh-CN/docs/guide/getting-started/packup)
5. 插件升级  
- [https://developer.ones.cn/zh-CN/docs/guide/getting-started/upgrade](https://developer.ones.cn/zh-CN/docs/guide/getting-started/upgrade)

规则：
- 未完成阅读，不开始编码与打包。
- 若文档不可访问，先向用户确认替代来源（本地镜像或截图）。

## 3. 先问 5 个关键问题（苏格拉底式）
开始任何开发前，先确认以下问题：

1. “这个插件最核心要解决的一个问题是什么？”
2. “页面上看到什么结果才算完成？”
3. “统计口径是什么（时间窗口、判定条件、时区）？”
4. “目标环境和团队是哪一个？是否只允许调用已确认可用端点？”
5. “交付命名是什么（插件名/包名/版本），验收证据要哪些（页面/HAR/日志）？”

若用户未明确回答，必须写出假设并得到确认。

## 4. 通用输入参数（避免硬编码）
不要在技能中写死本机路径、账号密码。统一用变量：

- `ONES_BASE_URL`：如 `http://172.16.80.61:30011`
- `ONES_PLUGIN_MODE`：`team` 或 `organization`
- `ONES_TEAM_UUID` / `ONES_ORG_UUID`
- `ONES_PLUGIN_NAME`：显示名
- `ONES_PLUGIN_ROUTE`：外部 API 路由段
- `ONES_PLUGIN_APP_ID`
- `ONES_PLUGIN_VERSION`
- `ONES_OUTPUT_DIR`：打包输出目录

凭据规则：
- 不在 skill 中存明文账号密码。
- 通过运行时输入或环境变量注入。

## 5. 环境预检
执行前先检查：

```bash
ones --version
node --version
npm --version
npx op --version
```

若 `ones` 未安装：
```bash
npm install -g @ones/cli --registry=https://npm.partner.ones.cn/registry/
```

平台补充：
- Mac/Linux：若 backend 依赖编译失败，先安装 `cmake`。
- Windows：确保 Node 安装包含 build tools（`node-gyp` 相关）。

## 6. 标准流程（Codex / OpenClaw 通用）

### 6.1 创建项目
```bash
ones create -d
# 或指定目录名
ones create -d <plugin-name>
```

### 6.2 添加 Settings 模块
```bash
npx op add module
```
- 选择 `settings`。
- 在 `config/plugin.yaml` 确认：
  - `service.mode`
  - 模块 `moduleType: settings`
  - 模块 `title` 已设置。

### 6.3 本地调试绑定
```bash
npx op login
npx op pickteam local     # team 模式
npx op invoke run
# 或仅后端
npx op invoke run --mode=backend
```

若 `plugin.yaml` 关键配置变更（API/模块/权限）：
```bash
npx op invoke clear
npx op invoke run
```

### 6.4 开发实现约束
- Frontend：
  - Settings 页面只做必要交互，不引入无关复杂度。
  - 明确 `loading/success/error` 三态。
- Backend：
  - API 返回结构稳定，错误信息可读。
  - 日志字段解析兼容嵌套结构与 JSON-lines 字符串。
- 路由：
  - 前后端路径必须与 `service.mode` 匹配。
  - 团队模式优先 `/project/api/project/...`。

### 6.5 打包
官方命令：
```bash
npx op packup
npx op packup --release
```

若项目封装了 npm 脚本，也可用：
```bash
npm run packup -- --bump no-modify
npm run packup -- --release --bump no-modify
```

## 7. 升级规则（必须）
- `config/plugin.yaml`：
  - `service.app_id` 必须保持不变。
  - `service.version` 必须递增。
- `config/upgrade.yaml`：
  - 升级场景必须存在且有效。
- 同版本重复上传可能失败（“该插件已存在”），先升版本再打包。

## 8. HAR-first 调试策略（强制）
1. 先跑一次完整路径并抓 HAR。
2. 从 HAR 建立“可用端点白名单”。
3. 代码只保留白名单端点；避免保留大量兜底探测。
4. 发布前再抓一份最终 HAR 作为证据。

## 9. 最小回归（每次发版必过）
1. 点击“开始统计”后，页面不出现“请求失败”。
2. 已知有近期日志/事件的插件，不会被误判为疑似未使用。
3. 刷新页面后，上次统计时间与结果仍可见。

## 10. 交付标准
必须交付以下内容：

1. 可安装包：`<PluginName>-<version>.opk`
2. 版本信息：`service.name / service.app_id / service.version`
3. 验证证据：
- 一份 HAR 或关键网络截图
- 一张最终结果截图
- 最小回归结论（3 条）

## 11. Codex 与 OpenClaw 兼容说明
- 本技能只使用通用 shell 流程，不依赖单一平台专属语法。
- Codex 可额外做自动浏览器验证；OpenClaw 无浏览器时可改手工验证并保留截图/HAR。
- 若某工具不可用（如浏览器自动化、SSH、MCP），需显式说明并切换到可执行替代步骤。

## 12. 常见问题速查
- 404：
  - 优先检查路由前缀和 `service.mode` 是否一致。
  - 对照 HAR，移除不可用 fallback 端点。
- 400：
  - 查看响应体字段错误，按环境实际 schema 调整查询字段。
- 升级不生效：
  - 检查版本是否递增、`upgrade.yaml` 是否有效、前端资源是否加载新版本路径。

