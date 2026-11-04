# COMSOL 6.3 执行器

实际实现位于 `comsol_workflow/comsol63.py`，编排和审批位于 `comsol_workflow/workflow.py`。通用 Skill 不依赖 Java 标签；只有案例与此适配层理解 COMSOL 6.3。

支持 Windows、已审阅的 MPH、既有求解序列、实数全局指标。执行链为 `comsolcompile.exe` → `comsolbatch.exe`；使用 `ModelUtil.loadCopy` 加载副本，在独立运行目录保存 `solved.mph`、`metrics.csv` 和日志。无需第三方 Python 桥接，不连接现有 GUI 或本地服务器。现有模型依赖的模块仍需有效许可。

生成 Java 代码在开始求解前检查运行版本为 6.3、研究/解/数据集标签存在、Solution 数据集关联指定解、清理清单覆盖全部 solution/store，以及覆盖参数已存在。只要一项失败便停止。清除保存解后调用原 `sol1.runAll()` 类似的完整序列；导出数据集不隐式换成其他解，复数指标明确拒绝。

参数覆盖仅接受 `scope=physics_scalar` 的有限数值及受支持单位。影响几何、选择、网格或求解结构的修改应先生成并审阅新的 MPH。此范围由工程师审查，不能单靠字段名称证明。

## 扩展与配置

[配置模板](../../templates/model-configuration.template.md) 提供新建模型/修改模型的可审阅记录。自动 builder、场图、复数求解、远程服务器、LiveLink for MATLAB 均为后续适配项。任意 COMSOL Java 导出可能包含 `runAll()`、研究运行和自定义方法；不能把它直接作为免审批构建脚本执行。

实现新 builder 时，将 build、inspect、solve、export 分成独立入口；先用经授权的模型和官方 6.3 文档确认 feature/property，不自动猜测接口字符串。需要原始 CAD、材料表、插值数据或零件库时，在 `model.dependencies` 声明并进行指纹记录；公开发行包不复制厂商模型与私有资料。

## 已知边界

- 静态参数/单位检查只检查案例里的覆盖，不解析 MPH 二进制内部所有表达式。
- `doctor` 只检测路径，不查询许可、不启动 COMSOL、不确认补丁版本。运行版本在 Java 日志中记录。
- 只有提交到 CSV 的指定时间点/扫描坐标受完整性检查；内部步长、迭代残差和场图须按工程验证计划审阅。
- 退出码、当前运行完成令牌、MPH、CSV 有效性共同决定执行完成；这些证据不证明守恒、网格独立性或实验有效性。
- 审批是可信本地工作区的审计记录，不是抵御恶意本地文件篡改的身份认证系统。普通工程变更会使计划哈希失效。
- 超时会尝试终止 Windows 进程树，并记录失败；新尝试需新计划。无自动调参/重试。

API 文档和软件许可路线见 [接口依据](../../docs/interface-sources.md)。
