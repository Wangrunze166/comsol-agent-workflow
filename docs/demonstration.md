# 演示说明

## 演示 A：无 COMSOL 的离线流程

使用 `examples/offline` 的合成数据演示工作流检查和结果比较。数据用于观察正常、异常和拒绝行为，不是 COMSOL 计算结果，也不是热电案例的实测数据。

```console
python -m comsol_workflow --help
python -m comsol_workflow compare examples/offline/actual.csv examples/offline/reference.csv --coordinate time_s --atol 0.01 --rtol 0.001
python -m comsol_workflow diagnose examples/offline/solver-synthetic.txt
python -m unittest discover -s tests -v
python -m comsol_workflow plan examples/thermoelectric-pid/case.json --out runs/offline-review
```

最后一条产生 `REVIEW.md`、`case.snapshot.json`、生成的 Java、`plan.json`、待审批模板和 `report.md`。模型和 COMSOL 路径缺失会列为阻塞条件，`report.md` 为 `not_executed`。重复运行请使用新的空目录。

按实际命令帮助运行示例比较、检查单位错误、缺失输入与失效审批。演示的合格结果包括正确拒绝不完整案例；“被阻止”是预期行为，不应将占位输入修改成假模型以绕过检查。

测试与校验状态见 [本次验证记录](validation-status.md)。该演示不启动 COMSOL，不检查许可，也不证明求解器能够收敛。

## 演示 B：热电模块与 PI 控制

参考 [COMSOL 官方案例 102421](https://www.comsol.com/model/lumped-thermoelectric-module-with-pid-control-102421) 和 [官方案例说明](https://www.comsol.com/model/download/1479601/lumped_thermoelectric_module_PID_control.pdf)。公开仓库只提供案例元数据与复现流程，模型由使用者按许可从官方来源取得。

已经恢复的参考配置如下，实际执行仍以使用者审核后的输入 MPH 与 Java 导出为准：

| 项目 | 参考配置 |
|---|---|
| 几何 | 3D 空气域、8 片散热翅片、底座、热电模块、接触层、电子器件 |
| 空气域 | 200 × 400 × 120 mm |
| 底座与翅片 | 底座 100 × 100 × 4 mm；翅片高 38 mm、热学厚度 2.5 mm，壳表示 |
| 器件与模块 | 器件 15 × 15 × 5 mm；模块 40 × 40 × 4.5 mm，集总热网络 |
| 接触层 | 厚 2.5 mm |
| 环境与入口 | 20°C，空气入口 0.5 m/s |
| 热源 | 稳态 4 W；瞬态在 10 min 后开启，平滑宽度 2 s |
| 热电参数 | 最大电流 4 A，最大热流率 40 W，最大温差 70 K，电阻 2 Ω |
| 稳态 | 电流 0.5–3.5 A，间隔 0.5 A |
| 瞬态 | 0–60 min，输出每 2 min |
| 控制 | 设定值 6.5°C；kP = −0.05 A/K，kI = −0.005 A/(K·s)，kD = 0；电流限幅 0.01–4 A |
| 耦合次序 | 先稳态流场，再冻结流场求热学；瞬态加入控制积分变量 |

案例名称沿用 PID，以上配置实际为 PI。它不是随温度同步更新流场的全瞬态双向耦合。原模型中控制器的偏置和限幅表达式应完整保留，不能只凭此摘要重建。

准备与执行：

1. 获取有权使用的 6.3 模型，核验安装、模块、补丁版本与模型版本。
2. 按 `examples/thermoelectric-pid/case.json` 准备私有案例；填写真实 MPH、相关依赖和配置审阅证据。占位案例保持待补充状态，不能直接求解。
3. 核对研究与求解序列、参数、数据集和输出表达式。生成静态计划，确认假设后再审批实际计算。
4. 运行指定序列，导出完整扫描或时间序列与最终 MPH；对照基准文件前先核对单位与坐标。
5. 保存逐点比较、日志诊断和验证状态；明确网格、时间步、实验验证是否完成。

以 PowerShell 为例，先复制案例并填好实际路径：

```powershell
python -m comsol_workflow init private/my-case
# 编辑 private/my-case/case.json，或将公开案例复制到此处再修正相对路径。
python -m comsol_workflow validate private/my-case/case.json
python -m comsol_workflow doctor --root 'C:\Program Files\COMSOL\COMSOL63\Multiphysics'
python -m comsol_workflow plan private/my-case/case.json --out runs/review-001 --comsol-root 'C:\Program Files\COMSOL\COMSOL63\Multiphysics'
```

安装路径仅为示意，应替换为本机路径。审阅计划后，将 `approval_requests/assumptions.json` 和 `solve.json` 各自复制到私有 `approvals/` 目录。**人类先确认假设，再单独批准求解**：保留 `stage`/`content_digest`，记录 `approved`、`approved_by`、带时区的 `approved_at` 以及可追溯的 `decision_evidence`。智能体只能转录真实决定。新计划会产生新的指纹，不能沿用旧文件。

仅在上述两个决定真实发生后执行：

```console
python -m comsol_workflow run runs/review-001 --assumptions approvals/assumptions.json --approval approvals/solve.json
python -m comsol_workflow report runs/review-001
```

默认每个计划只尝试运行一次；失败、超时或修改后使用新目录重新计划。版本首次接入建议先批准稳态案例，再安排瞬态。继承的目标时间网格不等同内部积分步长。

输出含义：器件平均温度使用 `comp1.dom1`；模块热流率使用 `comp1.lts.TEM1.P`；模块温差使用 `comp1.lts.TEM1.DT`；瞬态控制电流使用 `comp2.u_in_ctrl`。数据集和标签必须在实际输入模型中确认。

历史项目已留下本机复现报告，但新执行器的计算状态以本仓库验证记录为准。历史参考有 COMSOL 6.3 补丁版本差异，也未开展网格、时间步独立性或实验验证；公开演示不继承超出这些证据的结论。

## 演示录屏建议

依次展示模型来源、案例清单、静态错误拦截、可读计划、两个人工检查点、真实求解记录、逐点比较和报告。若没有执行真实求解，在画面与说明中写“离线流程演示”，不使用模拟进度或合成曲线暗示真实计算已完成。
