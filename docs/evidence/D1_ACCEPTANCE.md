# D1 Acceptance Submission（由用户填写）

请不要复制课程原句。用自己的话填写；可以看笔记，但请标明“看笔记”或“闭卷”。

## D1-T1（目标：最高可支持 independent_pass）

1. 两分钟解释（约 180–300 字）：为什么“最可能购买”不等于“最会被邮件改变”？说明 `Y(1)`、`Y(0)`、ITE 为什么不可直接作为训练标签。

2. 四类人群表：分别写 persuadable、sure thing、lost cause、harmed 的 `(Y(1), Y(0))`、ITE 和是否应触达。

3. 独立迁移题（答案暂不提供）：把 treatment 改为“发送 20 元券”，outcome 改为“7 天净利润为正”。某用户无券利润为 30 元、有券利润为 24 元，但两种情况下都会购买。她属于哪类？若只按购买概率排序会有什么风险？

4. 手算独立题（答案暂不提供）：随机实验中 treated 100 人转化 18 人，control 100 人转化 12 人。写出样本 ATE；说明为什么不能据此断言任意一个具体 treated 用户的 ITE。

## D1-T2（目标：最高可支持 independent_pass）

5. 运行并粘贴末尾摘要：

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 scripts/inspect_d1.py
python3 -m unittest discover -s tests -v
```

6. 用自己的话复述项目契约：unit、T、Y、X、CATE、决策、为什么排除 Womens E-Mail、为什么 `visit/spend/segment` 不能作为当前模型的普通输入。

7. 有意义的修改：在 `scripts/inspect_d1.py` 输出中增加 binary subset 中 treatment/control 各自样本量（不是只增加注释），重新运行测试；提交 diff 或修改后的路径及输出。

8. 限制：写出随机化帮助解决的一件事，以及它没有自动解决的三件事。

## 提交格式

```text
提交证据 D1-T1：
- 模式：闭卷 / 看笔记
- 两分钟解释：...
- 四类表：...
- 迁移题：...
- 手算题：...

提交证据 D1-T2：
- 运行命令与关键输出：...
- 项目契约复述：...
- 修改与 rerun：...
- 随机化的帮助/限制：...
- 实际投入时间：...h
```

