# 📈 股票每日涨跌统计与资产分析小助手 (Stock Portfolio Tracker)

这是一个为不想暴露券商账户密码、只需按金额/碎股记录持仓的投资者设计的**轻量级股票每日涨跌分析工具**。

专为 UK / 多币种投资者设计（如使用 Trading 212、Revolut、Freetrade 等平台买美股/英股的场景）。

---

## ✨ 核心特性

- 🔒 **纯本地隐私安全**：绝不需要关联券商账户或输入任何 API 密钥/密码，仅根据您输入的金额或股数在本地计算。
- 💷 **全程 GBP (£) 统一核算**：
  - 资产市值、买入均价、实时现价、盈亏金额统一使用 **英镑 (GBP)** 展现。
  - **不考虑汇率波动干扰**：标的当日涨跌百分比严格锚定股票实际行情走势，当日盈亏额即为股票涨跌折算为英镑的净盈亏额，不再受汇率起伏的杂音影响。
- 📊 **双界面交互**：
  - **Terminal 终端看板**：随时一条命令 `./run.sh` 打印精美的实时盈亏表格。
  - **现代 Web 可视化面板**：`./run.sh web` 在浏览器中查看资产饼图、每日涨跌柱状图与明细。
- 📷 **每日历史快照**：支持保存每日收盘资产快照，跟踪长周期资产净值变化。

---

## 🚀 快速开始

当前目录：`/home/kael/agents-cli/agy_workspace/trading212-stocks-INVESTS`

### 1. 查看当前持仓与今日涨跌统计 (默认已配置好您的 1 GBP 现金 + 11.7 GBP GOOGL)
```bash
./run.sh
```

### 2. 启动可视化 Web 看板
```bash
./run.sh web
```
在浏览器中打开：[http://127.0.0.1:26212](http://127.0.0.1:26212)

---

## 🛠️ 常用命令

### 添加或更新股票持仓

**按金额输入（推荐）**：自动根据当前股价与汇率折算碎股股数并设置买入成本
```bash
# 添加 11.7 GBP 的 GOOGL
./run.sh add GOOGL --amount 11.7 --currency GBP

# 添加 50 USD 的苹果
./run.sh add AAPL --amount 50 --currency USD

# 添加英股 (以 .L 结尾，如壳牌石油)
./run.sh add SHEL.L --amount 30 --currency GBP
```

**按具体股数输入**：
```bash
./run.sh add TSLA --shares 0.25 --cost 50 --currency USD
```

### 移除股票持仓
```bash
./run.sh remove AAPL
```

### 调整现金余额
```bash
# 设置 GBP 现金为 5 镑，USD 现金为 10 刀
./run.sh cash --gbp 5.0 --usd 10.0
```

### 保存与查看每日历史快照 (含纽约时间备注与持仓详情)
```bash
# 记录当前快照 (自动记录系统时间、纽约时间及交易状态、当时各股票持仓与市值)
./run.sh snapshot

# 查看历史快照列表
./run.sh history

# 查看某次历史快照的详细股票持仓与估值明细 (支持序号 1, 2... 或 快照ID)
./run.sh history 1
./run.sh history snap_20260918_133939
```
> 💡 **Web 端交互**：在浏览器打开 Web 看板后，直接点击「每日历史快照」表格中的任意一行，即可弹出全屏卡片，查看该记录时刻的所有持仓股票、精确股数、英镑现价、买入成本与单日盈亏！

### 🔍 数据双向交叉核验 (Two-Way Verification)
```bash
# 执行双向闭环核验，确保股数、均价、本金、现价与总资产 100% 自洽
./run.sh verify
```

---

## 📁 配置文件与数据结构

- `portfolio.json`: 存储您的持仓与现金配置（可随时直接用文本编辑器编辑）：
  ```json
  {
    "base_currency": "GBP",
    "cash": {
      "GBP": 1.0,
      "USD": 0.0
    },
    "holdings": [
      {
        "symbol": "GOOGL",
        "name": "Alphabet Inc. (Class A)",
        "shares": 0.044778,
        "cost_basis": 11.7,
        "cost_currency": "GBP"
      }
    ]
  }
  ```
- `history.json`: 存储每日收盘/记录的历史资产快照。

---

## ⏰ 自动每日统计（可选 Cron 定时任务）

如果您希望每天美股收盘后（英国时间约 21:30）自动记录快照并发送通知，可以添加到 crontab：
```bash
# 每天英国时间 21:30 自动执行一次快照
30 21 * * 1-5 cd /home/kael/agents-cli/agy_workspace/trading212-stocks-INVESTS && ./run.sh snapshot
```
