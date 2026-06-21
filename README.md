# 多因子策略平台

> 本地运行的 Streamlit 应用，直连 LQTP 因子数据库，实现因子扫描→策略构建→组合输出

## 快速开始

```bash
git clone https://github.com/tapmeswavk/MultiFactorPlatform.git
cd MultiFactorPlatform
pip install -r requirements.txt
streamlit run app.py
```

打开浏览器 → 填 LQTP 账号密码 → 登录 → 开始扫描因子 → 构建策略 → 输出组合 CSV → 上传 LQTP 回测。

## 架构

```
多因子平台/
├── README.md              # 本文档
├── requirements.txt       # streamlit, grpcio, protobuf, pandas
├── app.py                 # Streamlit 主入口
├── lqtp_connector.py      # LQTP gRPC 连接器 (token管理+因子调用)
├── factor_scanner.py      # 因子 IC 扫描器
├── strategy_builder.py    # 策略构建器 (截面标准化+加权)
├── portfolio_output.py    # 组合CSV输出
├── data/
│   └── proto/             # Proto stubs ✅ 已就位
└── cache/                 # 本地缓存 (IC结果/因子值)
```

## 数据流

```
用户登录 → LQTP获取Token
    │
    ▼
因子扫描 → RunFactor逐因子跑 → 提取IC/ICIR/覆盖率 → 排序展示
    │
    ▼
策略构建 → 选因子+设权重 → 截面标准化 → 加权合成公式
    │
    ▼
组合输出 → 逐日RunFactor → 截面Top-N → CSV文件
```

## 功能模块

### 1. 登录页
- 输入 username / password / server 地址
- 点击"登录" → 调 LQTP AuthService.Login 获取 token
- Token 存入 session_state，后续请求自动带

### 2. 因子扫描页
- 点击"开始扫描" → 拉取 ListFactors 获取全部因子
- 逐因子调 RunFactor(formula, analyze=True, 2024-2026)
- 在页面展示: 排名 | 因子名 | IC | ICIR | 覆盖率 | 有效概率
- 支持按 IC/ICIR/覆盖率 排序
- 每个因子带"添加"按钮
- 扫描结果本地缓存 (避免重复请求)

### 3. 策略构建页 (右侧面板)
- 已选因子列表，每个带权重滑块 (默认1.0)
- 因子数量显示
- "截面标准化"自动处理 (rank + zscore)
- 实时显示合成的策略公式预览

### 4. 组合输出
- 用户填: 标的数量(如50)、日期范围(如2026-05-01~2026-05-31)
- 点击"生成组合" → 对每个调仓日:
  - 逐因子调 RunFactor 获取当日截面值
  - 截面标准化 (rank → 0~1)
  - 加权合成 = Σ(weight_i × normalized_score_i)
  - 取 Top-N
  - 输出等权 CSV
- 下载按钮直接保存 CSV

## 关键技术点

### 截面标准化
```
对每个因子: rank() → 0~1 均匀分布
加权合成 = Σ(weight_i × rank_i) / Σ(weight_i)
最终得分再做一次 rank → 0~1
```

### 调仓逻辑 (避免前视偏差)
```
5月策略: 用4月30日收盘数据算出的因子值 → 选5月1日组合
T日因子 → T+1日组合
严格用 begin_date-1 的因子值决定 begin_date 的持仓
```

### 输出格式 (LQTP Portfolio 兼容)
```
trade_date,quote_time,symbol,value
20260501,0,000001.SZ,0.020000
20260501,0,000002.SZ,0.020000
```

## 开发计划

- [x] Phase 0: 验证关键前提 (截面因子值可获取 ✅)
- [ ] Phase 1: 搭建 Streamlit 框架 + 登录页
- [ ] Phase 2: 因子扫描器 (IC排名)
- [ ] Phase 3: 策略构建器 (选因子+设权重)
- [ ] Phase 4: 组合输出 (截面Top-N → CSV)
- [ ] Phase 5: 本地缓存 + 错误处理
- [ ] Phase 6: 测试 + 文档
