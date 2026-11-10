# Windows x64适配，0.4.4-beta

2026-10-12。沿用本地网页＋用户自填API方案；全部系统移除本机Codex／Claude接入，不调用真实模型，不修改现有用户凭证或历史。

已实现：原生msvcrt字节启动锁（Unix保留flock）；无SIGHUP系统的启动；Windows独占端口探测；资源管理器打开目录；Windows启动错误消息；无fchmod环境的配置保存；Windows备份发布拒绝覆盖；UTF-8源码bat与冻结运行时；Windows x64白名单打包、第三方许可、SHA256清单；手动Windows CI构建与合成PDF冻结冒烟。

交付形式：完整解压BackedUp目录后双击BackedUp.exe，保留控制台；网页退出服务，数据留在%LOCALAPPDATA%/BackedUp/data-v1。云模型按用户账号收费。自定义服务使用HTTPS OpenAI兼容协议，不承诺任意供应商协议自动兼容。API Key默认会话使用；持久化是本地文件，不宣称经过Windows ACL强化或加密。

本机可完成的验证：Windows锁获取／释放／超时分支模拟、中文目录打开参数、旧CLI设置及调用拒绝、后端与前端回归、现有macOS冻结包冒烟。Windows真实锁竞争、控制台关闭后的进程回收、资源管理器、中文路径、PDF原生依赖、SmartScreen和干净机器安装必须在Windows验证。

构建脚本scripts/build_windows.py只允许Windows x64，不在macOS生成假exe。工作流.github/workflows/windows-beta.yml仅workflow_dispatch，仓库以本项目为根目录；成功后上传测试ZIP，不自动发布Release。不依赖真实API Key，不包含个人PDF或输出目录。当前没有Windows运行环境，工作流未执行，Windows包尚未生成。

旧CLI故障脚本已停用，对应package-faults.json保留为0.4.3历史记录。当前API故障检查在tests/test_request_faults.py；冻结包无模型冒烟在scripts/smoke_package.py。

本轮结果：213项Python发现测试、8个前端语法检查、12组交互模拟通过；0.4.4 macOS冻结包启动、上传、解析、保存高亮报告、只读历史、重复启动与退出通过。删除已退役CLI测试后总数变化，不代表删减API回归。没有真实模型调用。Windows构建和CI尚未执行。
