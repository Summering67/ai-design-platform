## ADDED Requirements

### Requirement: 固定用户邮箱密码登录

系统 SHALL 只允许预置用户 `developer@local.test` 通过邮箱密码登录，密码 SHALL 只从必需的 `API_AUTH_FIXED_USER_PASSWORD` 运行环境变量读取。系统 MUST NOT 提供注册、找回密码、修改密码或第三方登录能力，且 MUST NOT 将密码写入数据库、migration、示例配置、HTTP 响应或日志。

#### Scenario: 固定用户成功登录

- **WHEN** 客户端向 `POST /api/auth/login` 提交固定邮箱和正确密码
- **THEN** 系统创建独立登录会话并返回固定用户的 ID、邮箱和显示名称

#### Scenario: 登录凭据无效

- **WHEN** 客户端提交其他邮箱、错误密码、空字段或未知字段
- **THEN** 系统返回稳定的无效请求或凭据错误，且不创建登录会话

#### Scenario: 固定用户密码缺失

- **WHEN** API 启动时未提供 `API_AUTH_FIXED_USER_PASSWORD`
- **THEN** 系统返回配置错误且不启动 HTTP 服务

### Requirement: 七天数据库登录会话

登录成功 SHALL 在数据库中创建当前登录上下文独有的登录会话，并通过会话 Cookie 识别后续请求。每个登录会话 SHALL 自创建起固定有效 7 天，认证访问 MUST NOT 延长其过期时间；同一用户 SHALL 能同时拥有多个登录会话。

#### Scenario: 会话在固定期限内使用

- **WHEN** 客户端在登录会话创建后的 7 天内多次访问受保护资源
- **THEN** 系统识别同一用户，且登录会话的过期时间保持不变

#### Scenario: 多浏览器同时登录

- **WHEN** 固定用户在两个浏览器分别成功登录
- **THEN** 系统创建两条可独立使用和撤销的登录会话

#### Scenario: 会话到期

- **WHEN** 客户端使用已超过固定 7 天期限的登录会话访问受保护资源
- **THEN** 系统返回 HTTP 401 与 `unauthorized`，且不处理受保护业务操作

### Requirement: 当前用户与单会话退出

系统 SHALL 通过 `GET /api/auth/me` 返回当前登录用户资料，并通过 `POST /api/auth/logout` 撤销当前登录会话。退出 MUST NOT 撤销同一用户的其他登录会话。

#### Scenario: 查询当前用户

- **WHEN** 有效登录会话请求 `GET /api/auth/me`
- **THEN** 系统返回固定用户的 ID、邮箱和显示名称

#### Scenario: 退出当前会话

- **WHEN** 有效登录会话请求 `POST /api/auth/logout`
- **THEN** 系统撤销当前会话并清除当前会话 Cookie，后续使用该会话访问时返回未认证

#### Scenario: 退出不影响其他浏览器

- **WHEN** 用户退出一个浏览器中的登录会话后使用另一浏览器的有效会话访问
- **THEN** 另一登录会话继续有效

### Requirement: 公开与受保护访问边界

Web 首页 `/` 与登录页 `/login` SHALL 公开访问，工作台 `/workspace` 和 `/workspace/{projectId}` SHALL 要求登录。API 健康检查与 `POST /api/auth/login` SHALL 公开访问；当前用户、退出、项目、消息和 generation 接口 MUST 要求有效登录会话。

#### Scenario: 匿名访问公开页面

- **WHEN** 未登录访问首页或登录页
- **THEN** Web 正常展示目标页面且不要求先建立登录会话

#### Scenario: 匿名访问工作台

- **WHEN** 未登录访问 `/workspace` 或 `/workspace/{projectId}`
- **THEN** Web 跳转到登录页并保留原目标地址供登录后恢复

#### Scenario: 匿名访问业务 API

- **WHEN** 请求未携带有效登录会话访问当前用户、退出、项目、消息或 generation 接口
- **THEN** API 返回 HTTP 401 与 `unauthorized`，且不读取或写入业务数据

#### Scenario: 匿名访问健康检查

- **WHEN** 请求未携带登录会话访问存活或就绪检查
- **THEN** API 继续按健康检查契约返回服务状态
