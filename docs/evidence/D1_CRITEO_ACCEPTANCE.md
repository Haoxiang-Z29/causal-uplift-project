# D1 Criteo Acceptance（由用户完成）

## Final status

- `D1-T1`: `completed / independent_pass`.
- `D1-T2`: `completed / assisted_pass`.
- D1 packet: completed with mixed per-task quality; it is not labeled as one
  overall `independent_pass`.

## 已有用户证据

- `D1-T1` 已独立通过：潜在结果、ITE/ATE/CATE、response vs increment、
  四类人群、负 Uplift 和 treatment/outcome 迁移。
- `D1-T2` 已通过概念部分：随机化与混杂、consistency、overlap、
  interference、attrition、post-treatment leakage、measurement error、
  deployment shift，以及 Criteo 的 ITT/特征边界。

## Criteo 证据要求（现已完成）

1. 解释 `artifacts/d1_criteo_inspection.json` 中 treatment/control 样本量、
   conversion/visit 率、组间绝对差和 exposure 分布，不把组均值差说成个人 ITE。
2. 由用户在共享代码上增加总体 `treatment_ratio`、`conversion_rate` 和
   `visit_rate` 输出，并重新运行检查器和测试。
3. 复述最终契约：unit、T、primary/secondary Y、X、ITT estimand、决策、
   `exposure` 排除理由及匿名特征解释限制。
4. 提交实际投入时间。

## 运行命令

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 scripts/download_criteo.py
python3 scripts/inspect_criteo_d1.py
python3 -m unittest discover -s tests -v
```

Agent 生成和运行代码只证明 setup 可运行。用户已经完成解释、修改和 rerun，
因此 `D1-T2` 的任务状态为 `completed`；但部分结果解释经过提示且未用新例
独立复测，所以质量门槛保留为 `assisted_pass`。后续通过新场景迁移后才能
提升为 `independent_pass`，不需要重做整个 D1。

## 2026-08-04 evidence record

- User added the `overall` treatment/conversion/visit rates to
  `scripts/inspect_criteo_d1.py` and added matching fixture assertions.
- User-reported rerun: 5 tests passed; treatment ratio
  `0.8500001287591226`, overall conversion rate `0.002916680257907384`,
  overall visit rate `0.046992000911042324`.
- Agent verified the shared code and JSON artifact and independently reran all
  5 tests successfully.
- Result interpretation needed assistance on weighted overall rates and the
  exposure-selection explanation; final state is `completed / assisted_pass`,
  not `independent_pass`.
- User focused time: 6.5 hours.
