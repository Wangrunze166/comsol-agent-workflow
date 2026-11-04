# GitHub 发布步骤

## 发布前检查

只发布此仓库，不把相邻的私有案例或本机仿真交付目录加入 Git。检查实际跟踪文件列表，排除 MPH、CAD、客户数据、许可证、绝对路径、审批身份和运行日志。官方示例采用来源链接，不直接附带下载模型。

1. 阅读 `docs/validation-status.md`，确保每项状态对应真实记录；未进行的 COMSOL 求解明确写为未进行。
2. 运行当前版本的离线检查与测试，检查三个客户端入口均指向同一 Skill。
3. 核对许可证、第三方来源、示例数据性质和再分发范围。
4. 在发布说明中列出版本、支持平台/COMSOL 版本、已验证能力、已知限制和复现命令。

若发布首个版本，可标记为 `v0.1.0`，并明确其为面向已审阅模型的 MVP。

## 建库与推送

以下操作由仓库拥有者在完成上述检查并决定公开后执行。选择自己的 GitHub 组织、仓库名与远程地址；示例中的占位值需要替换。

```console
git init
git switch -c main
git add .
git diff --cached --stat
git diff --cached
git commit -m "feat: add COMSOL engineering workflow MVP"
git remote add origin https://github.com/YOUR-ACCOUNT/comsol-agent-workflow.git
git push -u origin main
git tag v0.1.0
git push origin v0.1.0
```

如果仓库已有历史，沿用现有分支和发布流程。`git add .` 前必须确认当前目录与文件清单；`.gitignore` 不能替代对已跟踪文件的检查。

## 发布说明内容

- **问题与能力：** 从已有、已审阅的 COMSOL 6.3 模型形成参数化计算、诊断与报告流程。
- **演示：** 离线合成数据流程；热电 PI 案例元数据及从官方获取模型的说明。
- **验证：** 给出本版本实际执行的检查，分别记录离线、编译、求解与工程验证。
- **限制：** 自建模型和新物理接口需要适配；原生客户端自动发现及不同补丁版本按验证记录说明。
- **许可：** 本仓库原创内容 MIT，COMSOL 与第三方内容不包含在授权中。

可为模型接入、错误报告和功能建议准备 GitHub Issue 模板，要求用户先删除私有数据与许可证信息。公开 CI 只运行离线检查；真实 COMSOL 测试应在有相应许可的受控环境中另行配置，禁止将许可证信息放入仓库。

版本发布状态以 [GitHub Releases](https://github.com/Wangrunze166/comsol-agent-workflow/releases) 和对应提交为准。发布说明中的求解与验证状态必须与实际证据一致。
