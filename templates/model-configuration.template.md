# 几何、物理场与数值配置审阅单

复制到私有案例目录。未确认项写入 `engineering.unresolved`，完成后将此文件路径加入 `model.dependencies`，使审阅记录随执行计划绑定。

| 配置 | 内容及来源 | COMSOL 6.3 中的证据/标签 | 审阅结论 |
|---|---|---|---|
| 问题与输出 | 工况、适用范围、指标与验收阈值 | 对应文档 | 待填 |
| 几何 | CAD来源、空间维度、长度单位、简化、装配/联合、接触间隙 | geometry/feature/named selections | 待填 |
| 选择集 | 每个域、边界和配对的预期数量、空间位置和用途 | 带标签截图或配置导出 | 待填 |
| 材料 | 各域/壳的属性、单位、函数范围、各向异性 | material/selection/property group | 待填 |
| 物理场 | 控制方程、未知量、适用假设 | physics tags与feature types | 待填 |
| 耦合 | 源/目标、单向/双向、稳态/瞬态反馈 | multiphysics/connector标签 | 待填 |
| 初值及边界 | 覆盖、重叠、符号、参考压力/温度、约束 | named selection/condition | 待填 |
| 网格 | 尺寸、边界层、曲率、薄层、质量、单元数 | mesh features和质量统计 | 待填 |
| 研究 | 扫描、时间表、激活物理场、上游解依赖 | study steps | 待填 |
| 求解器 | fully coupled/segregated分组、缩放、初值、线性solver、容差、时间步 | 完整solver sequence | 待填 |
| 后处理 | dataset绑定、表达式含义、单位、积分/平均范围 | dataset/numerical/export tags | 待填 |
| 许可与资源 | 所需模块、版本与补丁、核心、内存预估、超时 | 环境记录 | 待填 |

在 COMSOL 中更新几何后重新检查选择、材料和边界覆盖；更新网格后保存网格统计。自动编号不能作为跨几何版本的稳定标识。保存一个新的、明确命名的审阅 MPH，保留原始模型。配置导出作为证据，运行前检查其中是否夹带求解命令。

工程假设确认：谁确认、何时、针对哪个版本、具体决定。实际求解审批另行记录，不用本表的“审阅完成”代替。
