---
name: ones-ai-app-builder
description: 为 ONES AI应用发布平台 开发和打包可上传应用的技能。当用户要开发静态 ZIP、运行包 ZIP，或要求选择 runtime、处理本地数据库/外接数据库、生成 manifest.yaml 和 start.sh、输出可直接上传的 zip 时使用。
---

# ONES AI应用发布平台应用开发技能

用户要求“开发一个能上传到 ONES AI应用发布平台的应用”时使用这个技能。

## 什么时候用

适用于这些请求：

- 开发一个可上传到 ONES AI应用发布平台的应用
- 生成静态 ZIP 或运行包 ZIP
- 生成 `manifest.yaml`、`start.sh`
- 为 Node.js、Python、Go、Java 服务打包
- 处理本地数据库或外接数据库配置

## 工作流

1. 先判断应用类型：
   - 纯前端页面、报表、展示页：用静态 ZIP
   - 需要服务端进程或 API：用运行包 ZIP
2. 再判断运行时：
   - JavaScript / Node.js：`node20`
   - Python：`python311`
   - Golang：`go122`
   - Java：`java17`
3. 如果用户没说清楚，用最小可运行方案直接落地，不要先停在方案讨论。
4. 先读 [references/platform-spec.md](./references/platform-spec.md) 获取平台约束。
5. 优先复用 [assets/templates](./assets/templates) 下的模板，再按用户需求改造。
6. 生成代码时必须满足：
   - 运行包根目录直接包含 `manifest.yaml` 和 `start.sh`
   - 静态包根目录直接包含 `index.html`
   - 服务监听 `0.0.0.0`
   - `healthCheckPath` 返回 `200`
   - 本地持久化数据写 `/data` 或 `APP_DATA_DIR`
   - 外接数据库通过环境变量注入，不写死在源码里
7. 打包时优先运行：
   - `scripts/pack_app.sh <source_dir> <output_zip>`
8. 打包后必须运行：
   - `python3 scripts/validate_package.py --type <static|runtime> --zip <output_zip>`
9. 最终回复必须包含：
   - 产物目录
   - ZIP 路径
   - 包类型
   - 运行时
   - 是否用了本地数据库或外接数据库
   - 上传到控制台时该如何选择包类型

## 关键规则

- 不要把 ZIP 包成“顶层目录里再套一层项目目录”
- 不要在 `start.sh` 里启动多个长期后台进程
- 不要把本地数据库文件预打进 ZIP
- 不要把数据库密码写死到源码里
- 如果用户只说“做一个 demo”，优先做最轻量、最稳的可运行版本

## 数据库规则

- 本地数据库：优先 SQLite、H2、bbolt、LevelDB，文件统一放 `/data`
- 外接数据库：通过 `manifest.yaml` 的 `env` 注入连接信息
- 不要把 MySQL / PostgreSQL 服务和业务进程一起塞进同一个 ZIP

## 参考与资源

- 平台约束与决策表： [references/platform-spec.md](./references/platform-spec.md)
- 静态模板： [assets/templates/static-basic](./assets/templates/static-basic)
- Node.js 模板： [assets/templates/runtime-node](./assets/templates/runtime-node)
- Python 模板： [assets/templates/runtime-python](./assets/templates/runtime-python)
- Go 模板： [assets/templates/runtime-go](./assets/templates/runtime-go)
- Java 模板： [assets/templates/runtime-java](./assets/templates/runtime-java)
- 打包脚本： [scripts/pack_app.sh](./scripts/pack_app.sh)
- 校验脚本： [scripts/validate_package.py](./scripts/validate_package.py)
