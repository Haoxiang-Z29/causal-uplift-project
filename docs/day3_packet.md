# D3 日包：Response、S-Learner 与 T-Learner

## 0. 状态与证据边界

| 项目 | 当前值 |
|---|---|
| 日包目标 | 在 D2 固定切分上完成 response / S / T 的同台 validation 比较 |
| 数据 | Criteo unbiased v2.1；D2 派生数据 6,149,755 行 |
| 只允许模型选择的数据 | train + validation |
| D3 禁止使用 | test；留给 D4 冻结方案后一次性评估 |
| 当前真实模型结果 | **无**；脚手架与合成测试不等于 Criteo 模型证据 |
| 依赖实测 | Python 3.12.13；NumPy 2.5.1；pandas 3.0.5；scikit-learn 1.9.0；Matplotlib 3.11.1 |

## 1. 六小时路线

| Block | 时间 | 为什么现在做 | 输入 | 可观察输出 | 后续用途 | ownership |
|---|---:|---|---|---|---|---|
| 1 Learner anatomy | 45m | 先分清“响应概率”和“因果差” | D1 潜在结果 | 三种 score 的公式与手算 | 防止把 response 写成 uplift | `must_own` |
| 2 Response baseline | 60m | 建立普通定向基线 | 固定 train | `mu1_hat` 与 response AUC/排序 | 回答“为何高响应不等于高增量” | `must_own` |
| 3 S-Learner | 90m | 用一个模型造两个反事实副本 | `[X,T,T*X]` | `s_mu1/s_mu0/s_uplift` | 第一条 uplift 排名 | `understand → must_own` |
| 4 T-Learner | 90m | 检查分臂建模的偏差/方差权衡 | treated/control train | `t_mu1/t_mu0/t_uplift` | 第二条 uplift 排名 | `understand → must_own` |
| 5 公平比较 | 45m | 只比较 score，不偷换数据/尺子 | 同一 validation、同一 p、同一指标 | results CSV + Qini 图 | D4 结果与失败分析 | `must_own` |
| 6 修改与验收 | 30m | 证明会定位、修改、重跑、解释 | 代码与结果 | 一次用户修改 + rerun + 解释 | ownership gate | `must_own` |

## 2. 三种 learner 到底学什么

记：`X` 是处理前特征，`T∈{0,1}` 是随机广告分配，`Y` 是 conversion。

| 方法 | 训练对象 | 排序分数 | 分数含义 | 不是 |
|---|---|---|---|---|
| Response baseline | treated 行上的 `Y ~ X` | `mu1_hat(x)` | 若投广告时的估计转化概率 | 因果效应 |
| S-Learner | 一套 `Y ~ X + T + T×X` | `mu1_hat(x)-mu0_hat(x)` | 同一模型在 `T=1/0` 两个副本上的概率差 | 个体真实 ITE 标签 |
| T-Learner | treated 一套 `Y~X`，control 一套 `Y~X` | `mu1_hat(x)-mu0_hat(x)` | 两个分臂模型的概率差 | 保证无偏的个体效应 |

核心统一式：

$$
\hat\mu_t(x)\approx E[Y\mid X=x,T=t],\qquad
\hat\tau(x)=\hat\mu_1(x)-\hat\mu_0(x).
$$

这里的 `mu` 模型常被称为 nuisance outcome model：它不是最终业务 score，
但它帮助构造最终的 treatment-effect score。

### 为什么 response baseline 只在 treated 上训练

本项目的普通定向问题是“如果给这个人投广告，他有多大概率转化”，因此 score
应是 `mu1_hat(x)`。若把 treatment/control 混合后又删掉 `T`，模型学到的是
`P(Y=1|X)` 的两种制度混合，业务语义更模糊。Criteo treated 约占 85%，treated-only
仍有足够训练样本。代码复用这一 treated 模型作为 T-Learner 的 `mu1` 模型，使比较
非常透明：response 用 `mu1` 排名，T-Learner 用 `mu1-mu0` 排名。

## 3. 手算：高响应为什么可能排错

假设模型对三位广告候选人给出：

| 用户 | `mu1_hat` 广告下转化 | `mu0_hat` 不投广告转化 | `tau_hat=mu1-mu0` | response 排名 | uplift 排名 |
|---|---:|---:|---:|---:|---:|
| A 忠诚用户 | 0.80 | 0.75 | +0.05 | 1 | 3 |
| B 可说服用户 | 0.45 | 0.10 | +0.35 | 2 | 1 |
| C 反感用户 | 0.30 | 0.40 | -0.10 | 3 | 4/不投 |
| D 温和可说服 | 0.35 | 0.15 | +0.20 | 3 | 2 |

预算只能投 1 人：response 选 A，估计新增转化 0.05；uplift 选 B，估计新增转化
0.35。差异不是 B 更“容易转化”，而是 B 的两个潜在结果均值差更大。

### S-Learner 的两份反事实输入

设标准化后 `x=[2,-1]`。脚手架使用 `[X,T,T×X]`：

| 副本 | 模型输入 |
|---|---|
| treated copy | `[2,-1, 1, 2,-1]` |
| control copy | `[2,-1, 0, 0, 0]` |

两份输入送进**同一个已拟合模型**：若输出 `0.08` 和 `0.03`，则
`s_uplift=0.08-0.03=+0.05`。不是用这个人的观测 `Y` 做减法。

### T-Learner 的不平衡权衡

| 维度 | S-Learner | T-Learner |
|---|---|---|
| 是否共享信息 | 是，一套模型 | 否，两套模型 |
| 小 treatment 信号 | 可能被主结果模式忽略 | 不会被同一损失中的大样本主效应淹没 |
| Criteo 85/15 不平衡 | 可借用全体样本，方差通常较小 | control 模型样本/转化更少，`mu0` 方差更大 |
| 异质性能力 | 取决于是否允许 `T×X`/非线性 | 两模型自然可不同，但差值也会叠加误差 |
| 谁必然更好 | 都不必然 | 都不必然 |

## 4. 实现契约

### 数据与泄漏边界

| 角色 | 列 |
|---|---|
| 普通 X | `f0`–`f11` |
| treatment | `treatment`，只承担 learner 的 T 角色 |
| 主结果 | `conversion` |
| 禁止作为 X | `conversion`, `visit`, `exposure`, `split` |

`StandardScaler.fit` 只能在 train 的 X 上执行；validation 只调用 `transform`。
scikit-learn 官方接口和本地 1.9.0 都确认 `fit/transform` 与 `predict_proba`
契约。逻辑回归不加 class balancing：这里需要条件转化概率的差，随意平衡类别会
改变概率尺度。当前 base learner 是带 L2 正则的 LogisticRegression；S-Learner
显式加入 `T×X`，否则线性 logit 的异质性表达过弱。

### 关键路径定位

| 目的 | 文件/函数 |
|---|---|
| 读固定 train/validation | `scripts/train_d3.py::load_train_validation` |
| S 输入 `[X,T,T*X]` | `s_learner_design` |
| 训练 response/S/T | `fit_learners` |
| 两次潜在结果预测与相减 | `predict_counterfactuals` |
| 复用 D2 IPW/Qini 口径 | `gain_and_qini`, `evaluate_ranking` |
| 防止 D3 偷看 test | CLI 只加载 train/validation，run record 断言 `test_split_used=false` |

### 执行顺序

先跑所有机械测试：

```bash
cd /Users/hx/dev/work2/causal-uplift-project
.venv/bin/python -m unittest discover -s tests -v
```

Checkpoint 1 通过后，可先做有明确 `debug_only` 标签的小样本排障。注意 Criteo
派生文件按 source order 保存且 treatment arm 并非随机交错，因此 debug cap 使用固定、
与 treatment/outcome 无关的行号哈希优先级从整个 split 抽样，绝不直接截取文件头部：

```bash
.venv/bin/python scripts/train_d3.py \
  --confirm-contract treated-response_s-learner_t-learner_logit_v1 \
  --max-train-rows 100000 --max-validation-rows 100000
```

小样本数值不能写入简历。接口/内存无误后，删掉两个 cap 才是 D3 全量 validation run：

```bash
.venv/bin/python scripts/train_d3.py \
  --confirm-contract treated-response_s-learner_t-learner_logit_v1
```

## 5. 预期输出与不变量

| 产物 | 预期内容 | D3 通过前必须检查 |
|---|---|---|
| `artifacts/d3/validation_results.csv` | response/S/T 三行同口径结果 | validation 行数和 propensity 相同；每行自带 `evidence_level` |
| `validation_predictions.csv.gz` | T/Y、response、两套 `mu1/mu0/uplift` | 每列 shape `(n_validation,)` |
| `validation_gain_curves.csv.gz` | 降采样后的 Gain/baseline/Qini 曲线点 | 所有模型起点 0；同人群终点 Gain 相同 |
| `validation_gain_curves.png` | 三条 `Gain-random baseline` 曲线 | 图例与方向正确；漂亮与否不决定是否保留 |
| `run_record.json` | 数据、版本、行数、契约、test 使用状态 | 全量证据必须 `evidence_level=full_validation`、`test_split_used=false` |

概率不变量：`0≤mu0,mu1,response≤1`。效应分数理论范围 `-1≤tau≤1`；代码还精确检查
`s_uplift=s_mu1-s_mu0`、`t_uplift=t_mu1-t_mu0`。正号表示模型估计广告增加
conversion 概率，负号表示估计广告降低 conversion 概率；它们都不是观测到的个体 ITE。

## 6. 公平比较与结果解释模板

固定以下五件事：同一 D2 split、同一 validation 用户、同一 outcome、同一 observed
validation propensity、同一 D2 Qini/top-10% 公式。不能给某模型换测试集、只挑最好 seed，
也不能因为 Qini 弱就改定义。

提交解释时用四句：

1. `response` 排的是 ___，S/T 排的是 ___；
2. validation 上主指标按从高到低为 ___，但差值尚未做不确定性检验；
3. S/T 的 top-10% overlap 或分数相关性说明 ___；
4. 最意外结果是 ___，可能原因至少有 ___ 与 ___，D4 将检查 ___。

弱结果也是合格的第一张表；隐藏弱结果才会破坏项目可信度。

## 7. 常见错误与诊断

| 错误 | 现象 | 为什么错 | 修复 |
|---|---|---|---|
| 把 response score 叫 uplift | 只产生一列 `P(Y=1)` | 没有 `mu0`，无法作因果差 | 明确叫 `mu1`/response |
| S 预测只跑一次 | 没有 `T=1/0` 两份输入 | 不能形成反事实差 | 明确构造两个副本 |
| T 模型只给各自臂预测 | 每人只有一个预测 | 每位 validation 用户都需 `mu1` 和 `mu0` | 两模型都预测全体 validation |
| scaler 在 validation 上 fit | validation 均值进入模型流程 | 数据泄漏 | train `fit`，validation `transform` |
| 用 `exposure` 当 T 或 X | 指标突然更好 | post-treatment 选择破坏 ITT 契约 | 只用 randomized `treatment` |
| class_weight=balanced 后直接相减 | tau 数值膨胀/概率失真 | 类别权重改变概率目标 | MVP 不加权；后续若加权需校准 |
| 用 test 挑模型 | test 指标被反复查看 | 最终泛化证据失效 | D3 只看 validation |
| Qini 终点不同 | 同一人群却不同 | 排序只改顺序，不能改总体贡献 | 检查漏行/不同 p/不同 Y |
| S 接近常数 | 排名弱 | 单模型可能忽略小 treatment 信号 | 检查 T/interaction；记录失败，不偷换测试 |
| T 极端波动 | `mu0` 不稳定 | control 仅约 15%，且 conversion 稀少 | 查 arm 事件数、正则与 D4 稳健性 |

## 8. 当天验收与证据提交格式

### Checkpoint 1：概念与契约（独立作答）

给三位候选人：A `(mu1=.70, mu0=.65)`，B `(.40,.10)`，C `(.25,.35)`。

- response 与 uplift 各自如何排序？预算 1 人各选谁？
- `tau<0` 的业务含义是什么？为什么不能说已观察到该人的真实 ITE？
- 在 response baseline 的两种候选契约中，为什么本项目选 treated-only `mu1`，而不是混合两臂后丢掉 T？

### Checkpoint 2：代码定位与预测

- 指出 S/T 各自生成 `mu1`、`mu0` 和相减的确切函数/代码。
- 在看到结果前预测：Criteo 85/15 下 S 与 T 谁更可能方差大，理由是什么？
- 预测删除 `T×X` 后 S-Learner 的异质性/排序会如何变化。

### Checkpoint 3：用户修改、全量 rerun、解释

在不改变 test gate 的前提下完成一个小修改。默认验收修改：为结果表新增每个排名
top-10% 的 control/treated conversion 数或 negative-uplift fraction，先预测影响，再写测试、
全量 rerun。Agent 生成代码不算用户修改。

提交模板：

```text
提交证据 D3：
1) 概念：<三种 score 与正负号解释>
2) 代码定位：<函数名/关键行，说明两次预测与相减>
3) 运行命令：<无 row cap 的命令>
4) 测试：<通过数>
5) 产物：<results / predictions / curve / run_record 路径>
6) 真实结果：<三模型同口径表，不省略弱结果>
7) 我的修改：<改了什么、事前预测、测试与 rerun>
8) 我的解释：<哪种排名更好、为什么可能如此、至少一个局限>
9) 实际专注时间：<D3 总计；不知道分项就不拆>
```

质量门槛：Agent 脚手架 + 合成测试只支持 `implementing / unassessed`；用户跟随提示跑通并解释
可支持 `assisted_pass`；能定位两次预测、独立修改/重跑并回答迁移题才支持
`independent_pass`。D3 不因代码存在自动完成。
