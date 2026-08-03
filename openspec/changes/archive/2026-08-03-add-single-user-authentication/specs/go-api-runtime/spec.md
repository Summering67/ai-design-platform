## MODIFIED Requirements

### Requirement: 强类型运行配置

系统 SHALL 使用 Viper 从可选 YAML 配置文件和带 `API_` 前缀的环境变量加载配置，并将结果解析为供其他模块使用的强类型配置值。环境变量 SHALL 覆盖配置文件中的同名配置；固定用户密码 SHALL 只从必需的 `API_AUTH_FIXED_USER_PASSWORD` 环境变量提供，所有敏感值 MUST NOT 出现在示例配置中。

#### Scenario: 环境变量覆盖配置文件

- **WHEN** 配置文件与环境变量同时提供同一项非敏感配置
- **THEN** 系统使用环境变量中的值启动

#### Scenario: 固定用户密码通过环境提供

- **WHEN** 进程环境提供非空 `API_AUTH_FIXED_USER_PASSWORD`
- **THEN** 系统将其解析为认证模块的强类型配置，且不在启动日志中输出该值

#### Scenario: 固定用户密码缺失

- **WHEN** 进程环境未提供 `API_AUTH_FIXED_USER_PASSWORD` 或其值为空
- **THEN** 系统返回明确的启动错误并且不启动 HTTP 服务

#### Scenario: 配置无效

- **WHEN** 服务地址、数据库连接、连接池配置或固定用户密码缺失或无效
- **THEN** 系统返回明确的启动错误并且不启动 HTTP 服务

#### Scenario: 示例配置不包含密码

- **WHEN** 开发者查看仓库中的 API 示例配置
- **THEN** 示例只说明应使用 `API_AUTH_FIXED_USER_PASSWORD`，且不包含密码默认值或示例密码
