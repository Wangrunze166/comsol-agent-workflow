# npm 0.2.1 发布核验

已公开发布到 [npm 官方注册表](https://www.npmjs.com/package/comsol-agent-workflow/v/0.2.1)。注册表记录的发布时间为 **2026-11-05 13:25:49（Asia/Shanghai）**，`latest` 已指向 `0.2.1`。

## 准确来源

- npm 分发版本：`0.2.1`；随包 Python 执行器：未改动的 `0.2.0`。
- 已审阅源码提交：[`6e7711131cd56289dce6bf732ccfba486656156d`](https://github.com/Wangrunze166/comsol-agent-workflow/commit/6e7711131cd56289dce6bf732ccfba486656156d)。
- [PR #3](https://github.com/Wangrunze166/comsol-agent-workflow/pull/3) 合并提交：`c0d685633efc87adaee0029185306823067d132d`。
- 公开 tarball：61 个文件，101,624 字节。
- SHA256：`80fe2aef88f5dcb268ce0171e1b4886040d9e3f7866a24af9b273cd91d44be27`。
- 注册表完整性：`sha512-8H8XfJXVIn6OdDXyggVjMtcwbKy/bdqPyhBVYsRKSd3dN3iadyi0mu/p0Tu1Jbpsx64guW23zbrqOrM2PoDJMQ==`。

## 已完成的检查

- 匿名读取注册表并下载公开 tarball，字节与发布前审阅的安装包完全一致；README 文本也一致。
- 在新目录、使用新 npm 缓存，从官方注册表安装准确版本；实际 npm 命令入口的 `--version`、`--help` 和合成 CSV 比较通过。
- 独立新缓存的 `npx comsol-agent-workflow@0.2.1 --version` 返回 `0.2.1`。
- [Windows/Linux × Python 3.10/3.13、Node 22 的 CI](https://github.com/Wangrunze166/comsol-agent-workflow/actions/runs/41972355892) 全部通过。每个组合包含 96 项 Python 测试和 7 项 npm 安装集成检查（Node 测试报告连同外层测试计数为 8）。
- 不含 COMSOL 软件、许可、MPH、私钥或审批收据。本次未启动新的 COMSOL 仿真。

## 自动元数据的已知偏差

本次通过 npm 11.16.0 发布已审阅 `.tgz`。npm 自动生成的版本元数据含 `_resolved` 本机打包路径；`gitHead` 被缓存外层 Git 仓库误填为 `d15b2d71befef01502175d153dabc283f95a8af6`。这两个字段不在原始安装包中，不能用这个 `gitHead` 定位本项目源码。源码依据以上已审阅提交和逐字节校验。

现有发布未撤销或覆盖。后续从已审阅项目目录执行 `npm publish .`，并检查公开元数据和 tarball，见[发布步骤](release.md)。

这些检查证明 npm 分发可安装、可调用。真实中断续算、原多物理场案例及完整工程验证的边界仍见[仿真验证状态](validation-status.md)。
