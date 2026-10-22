# D1 复习日包：Criteo 因果问题与项目契约

## 1. 状态卡

| 项目 | 当前状态 | 解释 |
|---|---|---|
| 日期 | 2026-08-03 至 2026-08-04 | 一个 D1 日包跨两次自然日 |
| 用户专注投入 | 6.5 小时 | 约 6 小时预算的合理浮动 |
| `D1-T1` | `completed / independent_pass` | 潜在结果与 response-vs-increment 已独立通过 |
| `D1-T2` | `completed / assisted_pass` | 数据契约和操作完成；部分结果解释经过提示 |
| D1 日包 | `completed` | 可进入 D2；不把两个任务合并成虚假的单一质量等级 |
| 权威状态 | `causal-interview-sprint-ledger.md` | 任务状态、证据和 blocker 以账本为准 |

## 2. 六个 Block 路线图

| Block | 为什么存在 | 输入 | 可观察输出 | 下游用途 | Ownership |
|---|---|---|---|---|---|
| 1 校准与 setup | 固定期限、证据规则和工作环境 | 目标岗位、时间、现有代码 | 账本、目录、可运行检查器 | 控制范围与真实性 | `agent_handled` + 用户确认 |
| 2 潜在结果 | 区分购买结果与广告因果效果 | Unit、T、Y | ITE/ATE/CATE 手算与解释 | D3 learner 输出 | `must_own` |
| 3 Response vs increment | 防止把高响应误当高增量 | 两个分群的处理/对照率 | 四类人群、Uplift 排序 | 预算分配 | `must_own` |
| 4 识别边界 | 判断组间差何时有因果含义 | 实验或观测分配机制 | 随机化、SUTVA、overlap、风险表 | D2 审计、D8 失败分析 | `must_own` |
| 5 数据与契约 | 锁定项目真正估计的问题 | Hillstrom/Criteo 取舍、真实字段 | Criteo unit/T/Y/X/estimand | 所有后续代码 | `must_own` |
| 6 修改与 rerun | 证明用户能操作关键路径 | Agent 脚手架、全量数据 | 用户修改 overall rates、5/5 测试、全量 rerun | D2 数据审计 | `must_own` 操作 |

## 3. 核心记号速查

| 记号 | 英文全称 | 中文含义 | Criteo 项目中的对应 |
|---|---|---|---|
| `i` | unit | 一个分析单位 | 一行匿名用户 |
| `X_i` | covariates | 处理前特征 | `f0`–`f11` |
| `T_i` | treatment | 随机处理分配 | `treatment∈{0,1}` |
| `Y_i(1)` | treated potential outcome | 如果分到处理组时的潜在结果 | 允许广告定向时是否 conversion |
| `Y_i(0)` | control potential outcome | 如果分到对照组时的潜在结果 | 阻止广告定向时是否 conversion |
| `Y_i` | observed outcome | 实际观测结果 | 只观察 `Y_i(1)` 或 `Y_i(0)` 之一 |
| `τ_i` / ITE | Individual Treatment Effect | 个体处理效应 | `Y_i(1)-Y_i(0)`；现实中不可同时观测 |
| ATE | Average Treatment Effect | 平均处理效应 | `E[Y(1)-Y(0)]` |
| CATE(x) | Conditional Average Treatment Effect | 特征为 x 人群的平均处理效应 | `E[Y(1)-Y(0)\|X=x]` |
| ITT | Intention-to-Treat | 按随机分组定义的处理效果 | assignment 的效果，不是实际 exposure 效果 |

### 因果推断基本问题

| 实际分组 | 可观察 | Counterfactual | 为什么 ITE 不能作为普通监督标签 |
|---|---|---|---|
| `T=1` | `Y(1)` | `Y(0)` | 同一用户没有未处理世界的结果 |
| `T=0` | `Y(0)` | `Y(1)` | 同一用户没有处理世界的结果 |

观测公式：

\[
Y_i=T_iY_i(1)+(1-T_i)Y_i(0)
\]

## 4. 二元结果的四类人群

| 类型 | `(Y(1),Y(0))` | ITE | 广告含义 | 默认动作 |
|---|---:|---:|---|---|
| Persuadable | `(1,0)` | `+1` | 只有处理才转化 | 优先处理 |
| Sure thing | `(1,1)` | `0` | 无论处理与否都会转化 | 可能浪费预算 |
| Lost cause | `(0,0)` | `0` | 处理也不转化 | 不处理 |
| Harmed / sleeping dog | `(0,1)` | `-1` | 处理反而阻止转化 | 抑制处理 |

边界：这张表帮助理解，但真实数据不能给每个用户直接贴上四类标签。

## 5. Response 与 Uplift

| 分群 | `P(Y=1\|T=1,X)` | `P(Y=1\|T=0,X)` | Response 排序依据 | Uplift | 有限预算选择 |
|---|---:|---:|---|---:|---|
| 忠诚客户 | 80% | 75% | 处理后响应最高 | `+5pp` | 否 |
| 犹豫客户 | 30% | 5% | 处理后响应较低 | `+25pp` | 是 |

| 问题 | 目标 |
|---|---|
| Response model | 谁本来最可能购买？ |
| Uplift model | 谁最可能因为处理而改变？ |

若每群 1,000 人：忠诚客户约新增 50 次，犹豫客户约新增 250 次。

## 6. 识别条件与数据风险

### 让随机组差具有因果含义

| 条件 | 一句话定义 | 违反示例 | 后果 |
|---|---|---|---|
| Randomization | T 在概率上独立于处理前特征和潜在结果 | 只给高购买意向用户发券 | 选择偏差/混杂 |
| Consistency | 实际接受 t 时，观测结果对应同一个清晰版本的 `Y(t)` | “优惠券”混有 10 元券和 100 元券 | Treatment 定义不一致 |
| Overlap / positivity | 每类 X 都有正概率进入处理和对照 | VIP 全部处理、从不进入对照 | VIP CATE 依赖外推 |
| No interference | 一人的处理不改变他人的结果 | 家庭共享券、社交传播 | 对照污染、结果依赖他人 T |
| SUTVA | 无隐藏 treatment 版本且无干扰 | 广告素材/频次未区分，且用户互相影响 | `Y(t)` 定义不稳定 |

### 随机化不会自动修复

| 风险 | 例子 | 为什么随机化无能为力 |
|---|---|---|
| Attrition | 处理组更容易退出，结果缺失 | 初始可比不保证留下的人仍可比 |
| Post-treatment leakage | 用广告后的 `visit` 预测 `conversion` | 模型提前看到处理后的信息 |
| Measurement error | 某系统漏记 conversion | 随机分组不修复错误测量 |
| Deployment shift | 训练来自旧渠道，部署到新渠道 | 实验内有效不等于新分布有效 |
| Interference | 广告竞价或家庭成员互相影响 | 一人的结果不再只由自己的 T 决定 |

## 7. Criteo 项目契约

| 契约项 | 当前定义 | 为什么 |
|---|---|---|
| Dataset | Criteo Uplift unbiased v2.1 | 更贴近广告 incrementality；避开官方披露旧版 leakage |
| Unit | 一行匿名用户 | 官方数据一行对应一名用户 |
| Treatment `T` | 随机 `treatment` assignment | 保留随机可比性和 ITT 含义 |
| Primary `Y` | `conversion` | 稀疏但更接近业务结果 |
| Secondary `Y` | `visit` | 更高频，可作诊断；不能作为 conversion 的 X |
| Covariates `X` | `f0`–`f11` | 匿名、稠密的处理前用户特征 |
| Estimand | assignment ITT CATE | `E[Y(1)-Y(0)\|X=x]` |
| Decision | 固定预算下按预计增量 conversion 排序 | 从估计连接到广告定向动作 |

### 字段边界

| 字段 | 因果角色 | 是否进入普通 X | 原因 |
|---|---|---:|---|
| `f0`–`f11` | 处理前协变量 | 是 | 广告决策前可用 |
| `treatment` | 随机 T | 否 | 它是处理，不是用户特征；S-Learner 可把 `[X,T]` 作为模型输入 |
| `conversion` | Primary Y | 否 | 预测目标 |
| `visit` | Secondary Y / post-treatment | 否 | 用于预测 conversion 会泄漏 |
| `exposure` | 实际有效曝光指示 / post-assignment | 否 | 非随机，不能直接替代 T |

### Treatment 与 exposure

| 比较 | 是否保留随机可比性 | 可以声称什么 |
|---|---:|---|
| Treatment vs control | 是 | assignment 的 ITT 平均效果 |
| Exposed vs control | 否 | 只是混合了曝光与选择机制的相关差异 |

`exposure` 是二元有效曝光指示，不是曝光次数。实际曝光可能依赖活跃度、
广告请求和竞价机会，这些因素也可能影响 conversion。

## 8. 真实数据检查结果

### 文件与 schema

| 检查项 | 结果 |
|---|---|
| Shape | `13,979,592 × 16` |
| Compressed bytes | `311,422,618` |
| SHA-256 | `2716e1bf...34f616dc` |
| Feature columns | `f0`–`f11` |
| Binary columns | `treatment, conversion, visit, exposure` |
| Empty strings in features | 0 |
| Tests | 5/5 passed |

### 实验臂统计

| 指标 | Control `T=0` | Treatment `T=1` | Overall / Difference |
|---|---:|---:|---:|
| N | 2,096,937 | 11,882,655 | 13,979,592 |
| Population share | 15.00% | 85.00% | 100% |
| Conversion count | 4,063 | 36,711 | 40,774 |
| Conversion rate | 0.19376% | 0.30895% | Overall 0.29167% |
| Visit rate | 3.82010% | 4.85434% | Overall 4.69920% |
| Exposure rate | 0% | 3.60367% | 不作为因果组差 |
| Assignment difference | — | — | Conversion `+0.11519pp`; visit `+1.03424pp` |

业务尺度：`+0.11519pp` 约等于每 10 万名实验总体可比用户新增 115 次
conversion。它是总体 assignment ATE，不是个人 ITE，也不是模型结果。

### 加权总体率

| 正确公式 | 错误公式 | 为什么 |
|---|---|---|
| `0.15×control_rate + 0.85×treatment_rate` | `(control_rate+treatment_rate)/2` | 两组占比不是 50/50 |

总体率更靠近 treatment rate，是因为 treatment 占 85%，与效果正负无关。

## 9. 常见错误速查

| 错误说法/做法 | 正确校准 |
|---|---|
| Treatment 组 36,711 次转化都是广告新增 | 其中混有 Persuadable 与 Sure thing；个体 `Y(0)` 不可见 |
| Harmed 在 treatment conversions 中 | Harmed 的 `Y(1)=0`，不在已观测 treatment conversions 中，但会降低 ATE |
| Overall 靠近 treatment 说明广告有效 | 靠近是 85% 权重造成；有效性看随机臂差 |
| Exposed 转化率高说明曝光因果有效 | Exposed 非随机，存在后处理选择偏差 |
| 把 visit 加入 conversion 模型 | Post-treatment leakage |
| 给 `f3` 命名为“年轻用户” | 特征匿名，不能编造业务语义 |
| 组间平均差是每个人的 ITE | 只能解释为总体/条件群体平均差 |

## 10. 用户操作证据

| 操作 | 路径/结果 | 所有权判断 |
|---|---|---|
| 增加 overall rates | `scripts/inspect_criteo_d1.py` | 用户实际修改 |
| 增加 fixture 断言 | `tests/test_inspect_criteo_d1.py` | 用户实际修改 |
| 快速测试 | 5/5 passed | 用户运行，Agent 复核 |
| 全量扫描 | 1398 万行成功 | 用户运行，Agent 复核 artifact |

## 11. 质量门槛为什么不同

| Task | 已证明 | 仍需后续自然复查 | 当前质量 |
|---|---|---|---|
| `D1-T1` | 独立手算、解释、广告/优惠券迁移 | 混合面试题中保持稳定 | `independent_pass` |
| `D1-T2` | 数据选择、契约、代码修改和 rerun | 新例中独立解释加权率、增量购买、exposure 选择偏差 | `assisted_pass` |

不需要重做 D1。D2 或 D9 遇到新场景独立通过后，可以单独提升 D1-T2。

## 12. 运行与证据入口

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 scripts/download_criteo.py
python3 scripts/inspect_criteo_d1.py
python3 -m unittest discover -s tests -v
```

| 需要查看什么 | 文件 |
|---|---|
| 权威任务状态 | `../causal-interview-sprint-ledger.md` |
| D1 验收证据 | `docs/evidence/D1_CRITEO_ACCEPTANCE.md` |
| 项目契约 | `docs/project_contract.md` |
| 真实 JSON | `artifacts/d1_criteo_inspection.json` |
| 来源与许可 | `docs/criteo_source_record.md` |
| Hillstrom 历史日包 | `docs/day1_packet_hillstrom_legacy.md` |

Hillstrom 的三臂、`segment`、Mens/Womens Email 和 `spend` 不属于本次用户
学习或验收内容，只作为早期回退 setup 保留。
