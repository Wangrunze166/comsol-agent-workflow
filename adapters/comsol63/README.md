# COMSOL 6.3 执行器

v0.2 实现位于 `comsol_workflow/comsol63.py`，编排在 `workflow.py`，签名在 `approvals.py`，参数依赖检查在 `scope.py`。通用 Skill 组织工程判断，版本专属执行器处理 COMSOL Java API。**接口已实现不等于真实求解或中断恢复已经实测通过**；完成证据见[验证记录](../../docs/validation-status.md)。

支持 Windows、已审阅 MPH、既有求解序列和实数全局指标；使用 `comsolcompile.exe` → `comsolbatch.exe`，无需第三方 Python 桥接，也不连接已有 GUI 或服务器。模型所需模块仍须有效许可。

## 检查、求解和恢复分开

| 操作 | 驱动行为 |
| --- | --- |
| `validate` | 只检查案例、单位和输入文件，不打开 COMSOL |
| `smoke` / `dry-run` | 独立 `SmokeDriver` 加载副本、核验标签和依赖；不求解、不重建几何／网格、不清解、不保存新 MPH |
| `run`，solve 计划 | 验证两份用户签名后，检查模型、写入允许的覆盖、清理声明的旧解，执行已审阅序列并导出 |
| `run`，resume 计划 | 从绑定的恢复快照 `loadRecovery`，调用 `continueRun`；保留恢复状态，不退回原始模型从头运行 |

驱动检查 6.3 版本、study/solver/dataset 标签、求解序列与研究关联、Solution 数据集关联、全部 solution/store 标签及覆盖参数存在性。版本识别兼容本机返回的完整本地化产品字符串。可选场图必须存在且绑定声明的数据集。

## 参数依赖按实际模型检查

`scope=physics_scalar` 仅表达意图。Java API 读取几何、网格及选择属性和全局参数表达式；Python 检查直接及传递引用。覆盖参数影响这些节点时阻断，并记录节点／属性路径。

未知属性类型、读取失败、不支持的作用域／函数间接引用不能当作“没有依赖”。对有参数覆盖的计划，无法完整判断时停止；无覆盖的已审阅模型可以保留原设置复用。这是对存储表达式的保守检查，不是任意 COMSOL 模型的符号正确性证明。

## 签名与文件输出

实际运行要求 Ed25519 签名的 assumptions 和 solve/resume 收据。签名绑定当前计划、动作和上游假设收据；手填 `approved:true` 无效。用户可自行在受信终端使用 [human-review.ps1](../../scripts/human-review.ps1) 完成首次新求解的检查、审阅、签名与执行。该脚本不是免审批入口，也不创建系统权限隔离；私钥、口令、公钥和执行器的信任边界见[审批安全说明](../../docs/approval-security.md)。

COMSOL 默认安全策略可能拒绝普通 Java 文件写入。驱动将检查清单、指标和表格通过带当前运行 token 的 stdout 载荷交给宿主；宿主核验后写入限定文件。MPH 和 PNG 使用 COMSOL 原生保存／导出接口。执行器不修改 COMSOL 安全设置。

`postprocess.field_plot` 指定既有场图标签和 PNG 文件名；`postprocess.table` 指定含单位的全局结果 CSV 文件名。PNG 格式、表格内容及 metrics 坐标／数值需要通过交付检查，复数指标明确拒绝。

## 恢复设置

批处理启用 `-autosave on -recoverydir`。可选 `execution.recovery_interval_seconds` 为 **1..3600 的整数**；执行器在 Stationary/Time 的 Advanced 节点设置：

- `recoverysaveforce=manual`
- `recoverysaveevery=<秒数>`
- `recoverysavinginfo=oneveryiteration`

依据 [COMSOL 6.3 Advanced](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_solver.51.17.html)。该参数是保存设置，不保证指定秒数到达时已有可恢复状态；只有 COMSOL 实际写出的恢复文件才可使用。

`resume` 将原失败运行中的真实恢复目录复制为新计划快照并记录摘要。恢复需新的 assumptions 和 resume 签名，原 solve 签名不能授权续算。缺失或无效恢复状态直接失败，不静默重新求解。

## 扩展与边界

[最小导热板](../../examples/minimal-heat-plate/README.md)提供已在本机运行的纯构建示例；它保存为空解，不属于真实求解证据。其他建模器仍需核验具体 feature/property，并将 build、inspect、solve、export 分开。任意导出 Java 可能含求解调用，不能直接作为免审批构建脚本执行。

新几何、材料、耦合和网格通过[配置模板](../../templates/model-configuration.template.md)审阅；外部 CAD、材料表及插值数据列入依赖和指纹。远程执行、任意模型自动建模、复杂场数据和复数导出需额外适配。

`doctor` 只检查路径；退出码、当前 token、MPH、指标及可选产物共同决定完成状态。成功导出不证明守恒、网格独立性或实验有效性。每个计划仅尝试一次，失败记录保留，新尝试或恢复另建计划。

官方来源见[接口依据](../../docs/interface-sources.md)。
