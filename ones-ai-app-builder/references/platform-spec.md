# 平台规范

## 1. 目标

这个技能面向 `ONES AI应用发布平台`，负责把用户需求变成可直接上传的 ZIP 包。

平台支持两类包：

- 静态 ZIP
- 运行包 ZIP

## 2. 决策表

### 2.1 什么时候选静态 ZIP

适合：

- 纯前端页面
- 报表页
- 展示页
- 依赖外部 API 的浏览器应用

要求：

- ZIP 根目录直接有 `index.html`

### 2.2 什么时候选运行包 ZIP

适合：

- Node.js / Python / Go / Java 服务
- 需要服务端逻辑或 API
- 需要本地数据库
- 需要访问外接数据库

要求：

- ZIP 根目录直接有 `manifest.yaml`
- ZIP 根目录直接有 `start.sh`

## 3. 支持的运行时

- `node20`：JavaScript / Node.js
- `python311`：Python
- `go122`：Golang
- `java17`：Java
- `shell`
- `busybox`
- `nginxalpine`

默认选择：

- JavaScript 服务：`node20`
- Python 服务：`python311`
- Go 服务：`go122`
- Java 服务：`java17`

## 4. manifest.yaml 规则

最小示例：

```yaml
name: sample-app
runtime: node20
port: 3000
healthCheckPath: /
cpu: 250m
memory: 256Mi
env:
  DEMO_MODE: "true"
```

必需满足：

- `runtime` 是支持值
- `port` 与服务监听端口一致
- `healthCheckPath` 可访问且返回 `200`
- `env` 是键值对

## 5. start.sh 规则

- 使用 `#!/bin/sh`
- 建议 `set -eu`
- 最后 `exec` 主进程
- 不要拉多个后台长期进程

正确示例：

```sh
#!/bin/sh
set -eu
exec node /workspace/server.js
```

## 6. 网络与健康检查

运行包必须：

- 监听 `0.0.0.0`
- 使用 `manifest.yaml` 中的端口
- 健康检查路径返回 `200`

## 7. 数据目录规则

平台为每个应用挂载：

- 宿主机：`/data/app/<appId>`
- 容器内：`/data`

运行包有环境变量：

- `APP_ID`
- `APP_DATA_DIR=/data`
- `RELEASE_VERSION`

要求：

- 所有持久化数据写到 `/data`
- 不要写到 `/workspace`
- 不要依赖 `/tmp` 持久化

## 8. 本地数据库规范

适合：

- SQLite
- H2
- bbolt
- LevelDB / RocksDB

要求：

- 数据文件必须创建在 `/data`
- 初始化逻辑必须幂等
- 升级必须兼容旧数据

示例路径：

- `/data/app.db`
- `/data/demo`

## 9. 外接数据库规范

推荐方式：

- 通过 `manifest.yaml` 的 `env` 注入数据库配置

示例：

```yaml
env:
  DB_HOST: "10.0.0.12"
  DB_PORT: "3306"
  DB_NAME: "demo"
  DB_USER: "app_user"
  DB_PASSWORD: "replace-me"
```

要求：

- 不要把数据库地址写死在源码里
- 不要把数据库密码写死在源码里
- 不要把数据库服务进程打进 ZIP

## 10. 语言级策略

### 10.1 JavaScript / Node.js

- 用 `node20`
- 默认生成一个最小 HTTP 服务
- 除非用户明确要求，否则不要引入复杂框架

### 10.2 Python

- 用 `python311`
- 默认生成最小 HTTP 服务
- 除非用户明确要求，否则不要引入重框架

### 10.3 Golang

- 用 `go122`
- 快速原型可用 `go run`
- 如果用户明确要更偏生产，优先本地编译 Linux 二进制再执行

### 10.4 Java

- 用 `java17`
- 快速原型可用 `javac + java`
- 如果用户明确要 Maven/Gradle/JAR，优先直接产出 `jar`

## 11. 打包规则

- 静态 ZIP：从内容目录内部打包，确保根目录直出 `index.html`
- 运行包 ZIP：从项目目录内部打包，确保根目录直出 `manifest.yaml` 和 `start.sh`
- 优先用 `zip -r -X`

## 12. 最终交付要求

技能执行后应交付：

- 项目目录
- ZIP 文件
- 说明选用的包类型和 runtime
- 说明上传时应选择的包类型
- 如涉及数据库，说明是本地数据库还是外接数据库
