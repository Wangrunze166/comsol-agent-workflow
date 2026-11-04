# 验证状态 · 2026-11-04

当前源码版本：0.2.0。**用户完成两阶段签署后，最小导热板已在本机 COMSOL 6.3.0.290 跑通加载检查、真实求解、PNG/表格导出和指标验收。两段计算流程合计69.63秒，不含人工填写时间。中断续算仍未实测。** 此结果属于独立单物理场验证例，不代表原多物理场研究案例已验证。

| 验证项目 | 实际结果 | 证据与边界 |
|---|---|---|
| Python 回归 | 96/96 通过 | Windows、Python 3.14.6、cryptography 50.0.2；签名为临时测试密钥，进程为模拟调用 |
| Ed25519 审批 | 回归与真实用户签署验签通过 | 两阶段原始收据及归档副本验签通过，归档逐字节一致；用户私钥和信任根的隔离仍是部署前提 |
| 最小导热板构建 | 本机通过，34.620 s | COMSOL 6.3.0.290；192单元，左右各一个不同边界，保存时 sol1.isEmpty=true；不是求解耗时 |
| 原生安全参数 smoke | 通过，27.37 s | 包含编译和批处理加载；T_hot 无几何/网格命中，无不完整项，无未支持项；未求解 |
| 原生几何/网格覆盖拒绝 | 按预期拒绝，28.64 s | 即便 scope=physics_scalar，仍命中 L→L_geom 的几何引用及 L/12、L/120 网格引用；未求解 |
| 原生错误标签拒绝 | 按预期拒绝，28.08 s | missingStudy 在加载检查阶段被拒绝；未求解 |
| 求解/恢复驱动 Java 编译 | 本机通过 | 两种生成分支均生成 class，包含图/表、恢复间隔配置和原生继续接口；编译不是执行 |
| CSV、令牌、日志与缓存 | 回归通过 | 零退出码不能替代当前令牌；缓存需完整证据并重新检查依赖；不降低 COMSOL 安全策略 |
| 恢复快照/失败不回退 | 回归通过 | 文件哈希与文件集绑定，新确认和 resume 签名；真实中断续算未测 |
| 完整真实求解、实际 PNG/表格 | **本机通过** | 平均298.1500000000019 K，解析均值298.15 K，绝对误差1.93×10⁻¹² K；PNG为1600×1000，表格与指标一致 |
| 本次运行耗时 | **签署后36.91 s** | 编译7.36 s、批处理29.48 s（含启动、求解、导出）；此前加载检查32.71 s，按阶段完整起止时间合计69.63 s |
| 实际交付完整性 | **通过** | 15个结果文件SHA256与运行记录一致；新MPH非空且区别于输入，当前令牌及1行指标覆盖匹配 |
| 工程验证 | **未执行** | 网格/时间步独立性、守恒和实验有效性不可从软件检查推导 |
| GitHub CI | **四个环境全部通过** | Windows/Linux × Python 3.10/3.13，各96项；[运行记录](https://github.com/Wangrunze166/comsol-agent-workflow/actions/runs/41833464791)，代码基线 `7f222ca` |
| 三客户端 | 通用入口与安装脚本已有 | 不声称已在Codex、Claude Code、Cursor三个原生客户端逐一完成真实任务 |

版本化、去除私人路径的文件摘要见 [validation-evidence.json](validation-evidence.json)。原始 native batch/launcher/progress 日志、MPH 和计划保存在私有目录；未把用户名、私人路径、签名身份或许可证加入公开包。

实测 [metrics.csv](../examples/minimal-heat-plate/verified-results/metrics.csv)、[带单位表格](../examples/minimal-heat-plate/verified-results/global-results.csv)、[独立证据摘要](../examples/minimal-heat-plate/verified-results/evidence.json)及[令牌日志摘录](../examples/minimal-heat-plate/verified-results/native-log-excerpt.txt)可公开复查。`batch.log`保留批处理启动记录，`launcher.log`包含开始/完成令牌，求解器正文位于`progress.log`；不声称三个日志各自包含全部信息。

![本机 COMSOL 导出的导热板温度场](../assets/minimal-heat-plate-temperature.png)

上图为本次原始PNG导出，左端293.15 K、右端303.15 K；均值验收通过不等于完成逐点场误差、网格独立性或守恒验证。正常完成后COMSOL已清理本次recovery内容，不能据此宣称真实中断恢复通过。

此次实机发现并处理：版本返回本地化文字；Java异常可能伴随退出码0；普通Java文件写入受安全策略限制；comsolcompile仅保留主class；普通geometry不支持part专属func调用；COMSOL加载时会生成热物性/辐射解析函数。因此检查读取真实表达式并按引用分析函数，未知/不完整依赖仍阻断覆盖。

[最小案例](../examples/minimal-heat-plate/README.md)与[完整演示](demonstration.md)提供复现步骤；[审批安全说明](approval-security.md)解释为何TTY不是身份认证，以及同账号任意执行权限下不能承诺绝对不可代签。
