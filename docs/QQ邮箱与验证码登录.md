# QQ 邮箱与验证码登录

用户和企业支持注册邮箱验证、账号＋邮箱＋验证码登录、邮箱找回密码，原密码登录保留。管理员使用原密码登录，不开放注册或邮件登录。

## 本地启动

在项目根目录运行：

```powershell
.\start_backend.ps1 -CheckConfig
.\start_backend.ps1 -Build
```

启动入口加载 `config/account-security.env`，再构建并启动后端。该文件已被 Git 忽略，不能放入 `src/main/resources`、提交到仓库或随源码上传。环境变量优先于文件值。缺失 JWT 密钥时首次生成并写回私有文件，后续启动沿用同一个值。直接使用 `java -jar` 不会自动读取这个私有文件。

项目已在本机私有配置中设置发件邮箱和授权码。迁移机器时，从 `config/account-security.env.example` 建立私有文件，填写自己启用 SMTP 的邮箱与授权码。配置采用字面量 `KEY=value`，不加引号、不使用 `export` 或变量展开；邮箱密码字段填写 SMTP 授权码。

QQ 配置为 `smtp.qq.com`、端口 `465`、`SMTP_SSL=true`、`SMTP_STARTTLS=false`，`SMTP_USERNAME` 与 `SMTP_FROM` 必须一致。保留 TLS 证书主机校验和超时，不打印 SMTP 会话或验证码。其他 SMTP 服务可通过环境变量覆盖；使用 587 时必须同时改为 STARTTLS 开启、SSL 关闭。

业务后端需要可用的 HBase：本机默认 `ZK_QUORUM=127.0.0.1`，应按实际集群地址配置。SMTP 单独测试不依赖 HBase。后续服务器预览已连接真实 HBase，管理员登录和岗位查询接口验证通过。

## 页面与接口

| 操作 | 页面或 POST 接口 | 参数 |
| --- | --- | --- |
| 用户／企业注册 | `/register.html?type=user` 或 `company` | 填写邮箱并先获取验证码 |
| 注册发码 | `/api/auth/register/code` | `accountType, username, email` |
| 完成注册 | `/api/user/register`、`/api/company/register` | 原参数加必填 `code`，企业仍需 `companyName` |
| 登录 | `/login.html?type=user` 或 `company` | 切换“密码登录”或“邮箱验证码登录” |
| 登录发码 | `/api/auth/email-login/code` | `accountType, username, email` |
| 验证码登录 | `/api/auth/email-login/confirm` | `accountType, username, email, code` |
| 找回发码 | `/api/auth/password-reset/code` | `accountType, username, email` |
| 重置密码 | `/api/auth/password-reset/confirm` | `accountType, username, email, code, newPassword` |

`accountType` 仅接受 `user`、`company`。验证码登录成功沿用密码登录的响应字段和 JWT。无需邮箱唯一性迁移，同一邮箱可对应多个账号，必须通过账号和类型确定登录身份。旧账号保留密码登录；已有注册邮箱的旧账号也可收码验证，无邮箱的旧账号不会自动补绑。

新注册接口不再接受缺失验证码的请求；调用方必须同步升级。上线此版本前已发送的找回验证码因新增邮箱与用途绑定而失效，重新获取即可。用户密码、业务数据和既有 JWT 不会因此批量变更。

## 验证码状态与错误

- 每个用途单独生成六位数字，10 分钟有效，至少间隔 60 秒发送，同账号同用途每小时最多 5 次。注册还按邮箱跨账号、跨账号类型限制相同的发送频率。
- HBase 只保存带服务器密钥的验证码摘要。注册挑战和邮箱限额存入幂等创建的 `recruit_email_code` 表；登录与找回状态保存在既有账号行。
- 先原子预留发送次数，再发送邮件；SMTP 接受后从 `pending` 转为 `ready`。失败码无法使用，发送次数不退回。若 SMTP 已接受但数据库写入失败，应重新获取验证码，不能将该次邮件视为可用。
- 验证码只能用于对应用途、类型、账号与邮箱。重发撤销旧码，五次错误验证后失效；成功消费不能重放。账号信息不匹配时使用统一错误提示。
- 注册先验证所有字段，再消费验证码，最后条件创建账号。创建失败不恢复验证码；先尝试登录以确认是否创建成功，未成功则重新获取。
- 登录验证码消费和密码错误次数清零采用同一个 HBase 行级条件写入。封禁、解封、重置密码使之前签发的登录验证码失效。重置密码不能解封账号，旧 JWT 被撤销。
- HTTP 400 表示参数／验证码无效，409 表示账号已存在，423 表示账号封禁，429 表示频率限制，503 表示配置、邮件或存储服务不可用。错误不返回授权码、验证码或底层连接信息。

## 测试

```powershell
mvn -f day08-backend/pom.xml test
python day08-backend/tests/account_ui_smoke.py
.\start_backend.ps1 -SmtpTest
```

前两项分别使用模拟 HBase／邮件和模拟浏览器 API，验证业务规则与页面行为，不连接真实 HBase，也不发送邮件。浏览器截图输出到 `day08-backend/target/account-ui/`。

最后一项显式启用 `QqSmtpIntegrationTest`，使用真实 Spring Mail 和应用邮件配置，向已确认的发件邮箱自身发送三封邮件。默认 Maven 测试跳过该项；集成测试只允许发送到 `995612169@qq.com`。测试中随机生成的验证码仅用于投递检查，不是任何业务账号的有效验证码。

2026-09-16 已完成 QQ SMTP 实测，注册、登录、找回三封邮件均被 SMTP 接受，邮箱所有者已确认三封全部收到。最终 Maven 构建通过，46 项后端测试通过，真实 SMTP 测试在默认构建中跳过，显式执行时通过；浏览器测试和 Windows／Linux 配置加载检查通过。

## 部署脚本

Linux 启动入口统一加载 `deploy/run/account_env.sh`，默认私有文件位置为 `$HOME/day08/config/account-security.env`，可用 `ACCOUNT_SECURITY_ENV` 覆盖。读取配置时不执行文件内容，环境变量优先，私有文件权限设为 `600`，缺失 JWT 时首次生成并保存。

`scripts/deploy.py` 会上传完整源码、嵌套页面和启动脚本，远端构建测试通过后才重启；不上传本机私有配置。部署前应将对应私有配置单独置于目标机器。后续已将构建产物部署至现有服务器进行预览，保留服务器原有 JWT 密钥；真实 HBase 的管理员登录、岗位查询和 QQ SMTP 连接认证均已验证。预览通过 SSH 隧道访问，未变更现有公网站点。真实集群重启、跨进程并发和服务器端完整注册／登录／找回邮件闭环仍需专门验收。
