# D4 日包：结果、失败分析与 Resume-Safe MVP

## 0. 状态与证据边界

| 项目 | 当前值 |
|---|---|
| 日包目标 | 冻结可复现的诚实 MVP，并通过简历/项目证据/研究备忘三件套的 application-package 门槛 |
| 覆盖任务 | `D4-T1`（结果与失败分析）、`D4-T2`（可复现性与 application-package gate） |
| D4-T1 状态 | `completed / independent_pass`（已关闭） |
| D4-T2 状态 | `implementing / assisted_pass`（Block 4/5 已通过，Block 6 未开始） |
| 本日包性质 | Block 1–5 为**已完成事实的复盘记录**，非教学预告；Block 6 为**待完成的教学与验收内容**，用户已主动推迟到面试准备阶段 |
| 禁止使用 | test（D3/D4 全程未读取 test split，见 §4 可复现性证据） |

## 1. 六小时路线与真实完成情况

| Block | 时间 | 为什么要做 | ownership | 完成状态 |
|---|---:|---|---|---|
| 1 干净入口重跑与完整性核查 | 45m | 排除 test 泄漏、确认可复现 | `must_own` | ✅ 已完成，见 §2 |
| 2 结果解读 | 75m | 把弱/反直觉结果讲清楚而不是回避 | `must_own` | ✅ 已完成，见 §3 |
| 3 失败切片 | 60m | 对一个意外结果给出≥2个可信原因 | `must_own` | ✅ 已完成，见 §3 |
| 4 可复现性 | 60m | 环境/步骤/契约/artifact/实验日志留痕 | `understand → must_own` | ✅ 已完成，见 §4 |
| 5 申请材料草稿 | 60m | 简历要点逐条映射证据；起草 1–2 页研究备忘 | `must_own` | ✅ 已完成，见 §5 |
| 6 application-package 门槛验收 | 60m | 90 秒项目概述 + 六项门槛终验 | `must_own` | ⏸ 未开始，用户主动推迟到面试准备阶段 |

## 2. Block 1：干净入口重跑与完整性核查（已完成）

用户执行了无 cap 的全量重跑，用真实证据回答了三件事：

- **split/seed 一致性**：重跑后的 `artifacts/d3/run_record.json`、`artifacts/d3/validation_results.csv` 与 D3 收尾时的产出经 `diff` 比对**逐字节相同**。
- **未在 test 上做过模型选择**：`train_rows=1,957,575`、`validation_rows=2,096,612` 精确等于 `artifacts/d2_audit_split.json` 中对应四个 treatment×outcome 单元格之和；仓库范围检索确认代码中唯一涉及字符串 `"test"` 的分支是 `train_d3.py` 里的被动禁用检查（`FORBIDDEN_D3_SPLIT`）与 D2 自己的审计聚合脚本，没有任何路径把 test 行读入 D3/D4 的 train/validation 缓冲区。
- **可复现性的技术理由**（用户自己给出）：凸优化（`LogisticRegression`）收敛到唯一全局最优解，训练过程不含 dropout/SGD 随机小批量等随机机制；本次运行未使用 `--max-train-rows`/`--max-validation-rows` 等 debug cap，数据加载是固定切片的全量读取；在模型权重逐位相同的前提下，NumPy 排序在相同输入下逐位可复现。

证据文件：`docs/evidence/D3_ACCEPTANCE.md` §"D4 rerun verification"。

## 3. Block 2+3：结果解读与失败切片（已完成）

### 3.1 outcome_auc 异常偏高的排查（真实发生的自我纠偏过程）

用户最初怀疑 `outcome_auc` 接近 0.90–0.95 是 train/test 泄漏的信号。经过对指标定义的复核：

- `outcome_auc = roc_auc_score(validation.outcome, score)` 衡量的是**纯结局预测能力**，而 response 的预测目标（`P(Y=1|X,T=1)`）与 S/T 的预测目标（两个潜在结果概率之差）本质不同，AUC 不能跨这三个模型公平比较。
- 数据集本身高度不平衡（conversion 率 < 1%），AUC 在这种场景下天然偏高，不需要泄漏也能达到这个数值。
- 真正适合跨模型比较增量排序质量的指标是 `qini_coefficient`，而非 `outcome_auc`。

用户据此推翻了最初的泄漏假说，正确定位到 Qini/gain 才是核心评估指标。

### 3.2 三模型公平比较结果

| model | qini_coefficient | top_raw_incremental_gain | outcome_auc | negative_score_fraction |
|---|---:|---:|---:|---:|
| response | 1228.9707 | 2375.3289 | 0.9494 | 0.0000 |
| s_learner | 1156.6673 | 2330.1627 | 0.8979 | 0.4173 |
| t_learner | 1163.0317 | 2363.1006 | 0.8935 | 0.1127 |

用户的正确解读：response 在当前 validation/模型配置下 Qini 数值最高，但三者差距相对 ~210 万行 IPW 加权计算而言较小，且未做显著性或跨 seed 检验，因此只能称"当前配置下 response 观测值最高"，不能称"response 显著更优"。

### 3.3 S/T 负增量分数比例：预测落空与两轮自我修正

- **事前预测**（D3 阶段）：T 的负分比例应高于 S（理由：control 仅约 15%，T 的独立分臂模型方差更大）。
- **实测结果**：S≈0.4173、T≈0.1127，方向与预测相反。
- **第一轮解释**（D3 收尾）：S 共享参数+全局 `T×X` 交互项 → 大面积浅负；T 完全解耦独立分臂 → 少数深负孤岛。用户主动标注此解释仅与汇总统计相容，未经负值分布验证。
- **第二轮解释**（D4，基于条件均值/中位数/分位数的真实分布诊断，见 `D3_ACCEPTANCE.md` 表格）：T 的负值分布均值比中位数更负，呈右偏重尾——多数 T 负预测很温和，少数极端更深，因此更准确的表述是"S 广而均匀负、T 窄而重尾负"，而非简单的"浅/深"。同时并列提出统计性假说：control 组更稀疏、正例更稀有，使 T 的独立线性模型 `μ0` 全局系数方差被放大。
- 用户主动选择在样本级验证（检查最极端行的实际特征值）之前停止，两个假说均如实标注为**待验证假说**，留给 D6/D8 决定是否补做。

证据文件：`docs/evidence/D3_ACCEPTANCE.md` §"D4 result interpretation notes"、§"D4 negative-uplift distribution diagnostic"。

## 4. Block 4：可复现性文档（已完成）

新增 `docs/evidence/D3_ACCEPTANCE.md` 完整记录：

- 环境版本锁定（Python 3.12.13、NumPy 2.5.1、pandas 3.0.5、scikit-learn 1.9.0、Matplotlib 3.11.1）；
- 从干净 checkout 到最终结果的完整运行顺序；
- seed/split 契约（split seed `20260804`、model seed `20260805`，均硬编码，不可运行期覆盖）；
- artifact 索引表（每个产物文件的产出脚本与内容）；
- 实验日志，包含真实发生过的 **arm-blocked 采样调试故事**：D3 debug run 的原始行号截断法恰好落入连续的 treated 数据块，触发 `fit_learners` 的双臂防御性检查并正确中止；修复方式是改为固定的、与 T/Y 无关的行哈希优先级采样（`_splitmix64`），并新增回归测试锁定该行为。

用户在本轮明确将这个调试故事与"outcome-blind split"做了区分：前者是 treatment 维度的排序/采样偏差（与 Y 无关），后者是保护 split 本身不被 outcome 标签影响的独立机制，两者不能混淆。

## 5. Block 5：申请材料草稿（已完成）

用户对简历与备忘中的每个术语要求自证来源，而非套用模板措辞，包括：

- ITT（randomized `treatment`）与 `exposure`（post-treatment、非随机）的区分；
- outcome-blind split 与 arm-blocked 采样 bug 的区分（见 §4）；
- 选择 `LogisticRegression` 而非更复杂模型的理由，从最初的"个人学习效率"校准为"可解释性优先、把有限冲刺时间集中在因果逻辑验证而非模型调参"的工程决策表述（对齐 `difficulty-control.md` 的优先级：因果正确性 > 端到端可跑 > 有效评估 > 失败分析 > 深度扩展）。

产出文件：

- `docs/resume_algorithm_track.md`：因果推断项目设为主项目；VLA 项目简化并如实标注服务器过期、结果未完全复现论文的局限；跨境学术合作项目按用户决定移除；教育背景与技能栏改写为算法方向；当前实习经历整条按用户决定删除（测试/开发性质，避免包装成算法相关经验）。
- `docs/prospective_research_memo.md`：对"已完成证据""公开数据观察""提案""需企业对齐"四类标签逐条分级标注，明确区分已完成的三基线比较（§3 已完成证据）与尚未运行的稳健性检验、X-Learner 对比、成本感知策略（§5 提案）。

## 6. Block 6：application-package 门槛验收（未开始，推迟）

Resume-MVP 六项验收标准（摘自 `roadmap.md`）：

1. 项目可从关键路径重跑；
2. response、S-Learner、T-Learner 在同一份held-out数据上做过比较；
3. 至少存在一个有效的 Uplift 指标；
4. 简历中每个名词和动词都能映射到代码、结果或解释；
5. 备忘录中每条论断都标注为已完成证据、公开数据观察、提案，或需企业对齐；
6. **用户能给出一个 90 秒的项目概述**。

前 5 项已有真实证据支持（§2–§5）。第 6 项尚未验证——这不是遗漏，而是你在本轮明确选择推迟到面试准备阶段再做。六项必须全部满足才能判定 D4-T2 完全通过，因此 `D4-T2` 目前记为 `implementing / assisted_pass`，Active checkpoint 停在 D4，不前移到 D5。

### 待补验收内容（面试准备阶段）

- **90 秒项目概述**：问题→为何 response 排序不够→数据设计→三个 learner→评估方式→观测结果→业务决策含义→局限→下一步；计时并修订。
- **门槛终验**：在不被喂答案的情况下，独立回答至少一个未见过的追问；确认口头表述与 `D3_ACCEPTANCE.md`/`prospective_research_memo.md` 的最新证据一致，不能口头夸大已备忘录中标注为"提案"的内容。

## 7. 当天证据提交格式（用于最终关闭 D4-T2）

```text
提交证据 D4-T2 Block 6：
1) 90 秒概述文本（或转录）；
2) 用时（是否在 90 秒内完成）；
3) 未被喂答案独立回答的追问及回答内容；
4) 口头表述与现有证据文件的一致性自查（是否有夸大提案为已完成的措辞）；
5) 是否需要修订 resume_algorithm_track.md 或 prospective_research_memo.md。
```

质量门槛：能背出一份提前写好的稿子只支持 `assisted_pass`；能在追问下不看稿、用自己的话讲清楚为什么某个 learner 输了、下一步验证什么，才支持 `independent_pass`，D4-T2 才可完全关闭并前移到 D5。
