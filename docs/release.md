# GitHub 发布步骤

当前源码版本为 **0.2.0**，正式发布状态以 [GitHub Releases](https://github.com/Wangrunze166/comsol-agent-workflow/releases) 和对应提交为准。源码版本号不表示 v0.2.0 已正式发布。已有 v0.1.0 标签及历史发布必须保留，不移动、不覆盖、不强推。

## 发布前检查

只发布本仓库；相邻的私有案例、原始日志和交付目录不进入 Git。检查实际跟踪文件，排除 MPH/CAD、客户数据、许可证、私人绝对路径、审批身份和签名秘密。官方模型以来源链接提供。

1. 核对[验证状态](validation-status.md)：离线测试、Java 编译、模型构建、load-only smoke、真实求解、恢复和工程验证逐项列示。未做的求解或恢复不得标为通过。
2. 安装审批可选依赖，运行当前测试与合成 CSV 比较，检查三个客户端入口指向同一 Skill。
3. 核对 Ed25519 信任边界、参数依赖阻断、API 未知读取拒绝、输出命名及恢复审批说明；不得把 TTY 写成身份认证。
4. 检查文档链接、原创 SVG、示例性质、MIT 许可和第三方内容来源。本轮工程参考只使用[已核验的 10K+ 项目](high-star-engineering-references.md)。
5. 公开 CI 运行离线检查；真实 COMSOL 验证需要有许可的受控环境，许可证不放入仓库或公开日志。

```console
python -m pip install -e ".[approval]"
python -m unittest discover -s tests -v
python -m comsol_workflow compare examples/offline/actual.csv examples/offline/reference.csv --coordinate time_s --atol 0.01 --rtol 0.001
git status --short
git diff --check
git diff --stat
```

用户若要补做真实求解证据，可在自己的受信终端使用 [scripts/human-review.ps1](../scripts/human-review.ps1)。该入口要求用户密钥和两次明确签名，不允许 Agent 代填；运行前按[审批安全说明](approval-security.md)建立实际权限边界。它不属于公开 CI。

## 提交与发布

仓库已有历史，沿用现有 remote 和审阅流程；不要重新 git init 或重建已有标签。审阅拟发布文件的完整差异，再暂存具体文件并提交。发布分支默认使用 codex/ 前缀；合并后的发布提交应可由 CI 和验证记录定位。

准备发布时先创建 GitHub 草稿，写清当前已验证能力与仍待完成的检查。若验证尚未完成，保持草稿，或明确作为预发布；不要把缺少真实求解证据的版本写成“COMSOL 全链路验证通过”。

正式发布 v0.2.0 前确认标签不存在，并选择已审阅的准确提交。以下仅为仓库维护者决定正式发布后的命令示意：

```console
git tag -a v0.2.0 <reviewed-commit> -m "COMSOL Agent Workflow v0.2.0"
git push origin v0.2.0
```

不要用 -f 重建标签。若 v0.2.0 已存在，核查其来源并选择下一个版本；不覆盖已有发布来隐藏变更。

## v0.2 发布说明应包含

- 独立 load-only smoke/dry-run，原生模型标签及几何／网格参数引用检查。
- 用户控制 Ed25519 密钥的独立 approve 流程；手写审批 JSON 不再授权运行，TTY 仅是交互约束。
- 基于原生 recovery 的新计划和 continueRun 路径，需要新签名，无静默从头求解。
- 可选 PNG 场图、含单位的 CSV 表格；stdout token 载荷避免降低 COMSOL 文件安全策略。
- 可选 recovery_interval_seconds，整数 1..3600；仅设置保存策略，不保证已产生可恢复状态。
- 最小导热板建模器和解析基准，以及精确区分构建、检查、求解的证据。
- 平台／COMSOL 版本、复现命令、未验证项目和迁移说明：旧手填收据不能用于 v0.2，必须重新计划并签名。

发布后核验公开 README、图示、下载内容、标签提交和 CI 链接；保留旧版本可追溯性。发行包不附客户模型、许可证、私钥或原始私人日志。

## npm 官方注册表发布

npm 包名为 `comsol-agent-workflow`，首个 npm 分发版本为 **0.2.1**；随包 Python 执行器保持 **0.2.0**。这两个版本分别标识分发入口与执行器，不移动已有 GitHub `v0.2.0` 标签。安装说明见 [npm 使用文档](npm.md)。

先审阅 `package.json` 的正向文件清单和实际打包结果，确认没有私钥、审批收据、机器配置、客户模型或未脱敏日志。运行离线测试和 npm 包测试，再把真实 tarball 安装到独立目录，验证帮助、案例初始化、合成数据比较、Skill 安装与失败退出码。

```console
npm test
npm pack --dry-run --json
npm pack
npm publish ./comsol-agent-workflow-0.2.1.tgz --dry-run --access public --registry=https://registry.npmjs.org/
```

维护者在浏览器完成 npm 官方登录及要求的验证；密码、令牌和验证码不进入仓库、聊天或发布记录。确认登录身份和包名归属后，发布已检查的同一个 tarball：

```console
npm login --auth-type=web --registry=https://registry.npmjs.org/
npm whoami --registry=https://registry.npmjs.org/
npm publish ./comsol-agent-workflow-0.2.1.tgz --access public --registry=https://registry.npmjs.org/
```

发布后从官方注册表重新读取版本和完整性信息，在新的测试目录从注册表安装该准确版本并调用 CLI。保存发布时间、发布账号、源码提交、包清单、tarball 哈希及安装验证结果；这些是分发证据，不替代 COMSOL 求解记录。

```console
npm view comsol-agent-workflow@0.2.1 version dist.integrity dist.tarball --registry=https://registry.npmjs.org/
npx --registry=https://registry.npmjs.org/ comsol-agent-workflow@0.2.1 --version
```

只有注册表读回与安装验证完成后才记录“已发布”。已发布版本不覆盖，后续修改使用新版本号。账号登录或发布验证尚未完成时，明确报告已准备的安装包和缺失步骤。
