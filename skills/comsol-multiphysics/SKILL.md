---
name: comsol-multiphysics
description: Prepare, review, run, and validate a COMSOL multiphysics simulation workflow from traceable engineering inputs, with human approval before solving. Use for COMSOL model reproduction or a scoped simulation study.
---

# COMSOL 多物理场工程工作流

从用户提供的工程证据建立可复现案例，再调用版本专属执行器。此 Skill 负责工程判断与交付；`comsol_workflow` 负责确定性检查、审批绑定和 COMSOL 6.3 执行。以仓库根目录为工作目录。

1. **恢复证据。** 先读当前项目、用户指定文件和既有报告，区分原始输入、保存解与本次计算。缺少关键模型信息时，只问一个最能消除歧义的问题；其余未确认项写入待办。读 [输入与建模](references/modeling.md)，产出带来源的案例配置。完成条件：每个物理场、几何、材料、边界、研究和输出要求有来源或明确的未确认状态。
2. **确认工程假设。** 将简化、耦合方向、材料适用范围、边界解释、验证标准列成可审核清单，生成只读执行计划。请用户确认具体假设；仅在人类确认后记录 assumptions 审批。模型或配置改变后重新计划和确认。
3. **配置模型。** 从已审阅的 MPH 复用配置。需要新建/更改几何、物理场、网格或求解器时，按 [输入与建模](references/modeling.md) 在 COMSOL 6.3 中完成并导出配置证据，再生成新 MPH 与计划。保留命名选择及单位。完成条件：输入模型、依赖、参数覆盖、求解序列、数据集和输出表达式均可定位。
4. **实际求解前审批。** 读 [执行与诊断](references/execution.md)，核对执行计划、资源上限与预计产物。取得针对当前计划的 solve 审批后才运行真实执行器。审批不能由智能体自行填写为已同意，也不能用离线检查代替。
5. **验证与交付。** 读 [验证与报告](references/validation.md)。检查进程结果、求解覆盖范围和导出数据，再执行预先约定的工程验证。交付输入哈希、计划、审批、环境、日志、数据、MPH 和报告。结论按证据区分：静态检查通过、接口编译通过、真实求解完成、数值复现通过、工程验证通过。

依据来源和当前证据作结论：未运行的模型保持未运行；软件成功退出不等于物理模型正确。重试、自动调参和扩大计算范围均需与现有批准范围一致；改变工程假设、求解配置或验证阈值时重新审核。

仓库使用、安装与版本适配见仓库根目录的 `README.md`；公共示例的出处和演示边界见 `docs/demonstration.md`。这些路径相对于项目工作目录，Skill 的 `references/` 路径相对于此文件。
