"""
多因子策略平台 — Streamlit 本地应用

用法: streamlit run app.py
"""
import streamlit as st
import pandas as pd, time, os

from lqtp_connector import LQTPConnector
from factor_scanner import FactorScanner
from strategy_builder import StrategyBuilder
from portfolio_output import PortfolioOutput

st.set_page_config(page_title="多因子策略平台", layout="wide")
st.title("多因子策略平台")

# ---- Session State ----
for key in ["token", "connector", "scan_df", "selected_factors", "output_df"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "selected_factors" else {}

# ===== SIDEBAR: Login =====
with st.sidebar:
    st.header("LQTP 连接")
    server = st.text_input("服务器地址", "118.89.191.220:50051")
    username = st.text_input("用户名", placeholder="输入邮箱/用户名")
    password = st.text_input("密码", type="password")

    if st.button("登录", type="primary"):
        try:
            conn = LQTPConnector(server)
            token = conn.login(username, password)
            st.session_state.connector = conn
            st.session_state.token = token
            st.success(f"登录成功")
        except Exception as e:
            st.error(f"登录失败: {e}")

    if st.session_state.token:
        st.info(f"Token: {st.session_state.token[:30]}...")

# ===== MAIN =====
if st.session_state.connector is None:
    st.info("请在左侧登录")
    st.stop()

conn = st.session_state.connector
scanner = FactorScanner(conn)
builder = StrategyBuilder()

tab1, tab2, tab3 = st.tabs(["因子扫描", "策略构建", "组合输出"])

# ===== TAB 1: 因子扫描 =====
with tab1:
    st.header("因子 IC 扫描")

    # Scan controls
    ctrl_col, _ = st.columns([1, 2])
    with ctrl_col:
        c1, c2 = st.columns(2)
        with c1:
            ic_begin = st.text_input("IC 起始日", "20240102")
        with c2:
            ic_end = st.text_input("IC 结束日", "20260615")
        neutralize_scan = st.selectbox("中性化", ["无", "市值", "行业", "行业+市值"],
                                        help="用 LQTP 内置 neutralization 处理因子公式后再算 IC")

    with ctrl_col:
        if st.button("开始扫描", type="primary"):
            neu_map = {"无": "", "市值": "size", "行业": "industry", "行业+市值": "both"}
            neu = neu_map[neutralize_scan]

            with st.spinner("正在拉取因子列表..."):
                factors = conn.list_factors()
                st.session_state.all_factors = factors
                st.success(f"获取 {len(factors)} 个因子")

            begin = int(ic_begin); end = int(ic_end)
            cached = scanner.load_cache()
            if not cached.empty:
                st.session_state.scan_df = cached
                st.info(f"从缓存加载 {len(cached)} 条结果")
            else:
                with st.spinner(f"扫描 {len(factors)} 个因子 ({ic_begin}~{ic_end}, 约需 {len(factors)*0.3:.0f}秒)..."):
                    progress_bar = st.progress(0)
                    status = st.empty()
                    def update(i, total, name):
                        progress_bar.progress(i / total)
                        status.text(f"[{i}/{total}] {name}")
                    df = scanner.scan_all(factors, begin, end, neutralize=neu, progress_callback=update)
                    scanner.save_cache(df)
                    st.session_state.scan_df = df
                    progress_bar.empty()
                    status.empty()
                st.success(f"完成! {len(df)} 个因子有效")
            st.session_state.scan_neutralize = neu  # remember for strategy

    # Results table + selection
    df = st.session_state.scan_df
    if df is not None and not df.empty:
        # Filter by IC threshold
        ic_min = 0.025
        df_filtered = df[df["abs_ic"] > ic_min].copy()
        st.caption(f"|IC| > {ic_min}: {len(df_filtered)} 个因子 (全部 {len(df)} 个)")

        center_col, right_col = st.columns([3, 1])

        with center_col:
            # Column header
            h1, h2, h3, h4, h5, h6 = st.columns([3, 1, 1, 1, 1, 0.8])
            with h1: st.caption("因子名称")
            with h2: st.caption("IC")
            with h3: st.caption("ICIR")
            with h4: st.caption("有效%")
            with h5: st.caption("覆盖率")
            with h6: st.caption("选择")

            for i, (_, row) in enumerate(df_filtered.iterrows()):
                name = row["name"]
                uid = row.get("definition_id", str(i))
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 1, 0.8])
                with c1:
                    st.text(name[:50])
                with c2:
                    st.text(f"{row['ic']:+.4f}")
                with c3:
                    st.text(f"{row['icir']:+.3f}")
                with c4:
                    st.text(f"{row['eff']:.1%}")
                with c5:
                    st.text(f"{row['coverage']:.3f}")
                with c6:
                    if name in st.session_state.selected_factors:
                        if st.button("✅", key=f"rm_{uid}", help=f"移除 {name[:20]}"):
                            st.session_state.selected_factors.pop(name, None)
                            st.rerun()
                    else:
                        if st.button("＋", key=f"add_{uid}", help=f"添加 {name[:20]}"):
                            st.session_state.selected_factors[name] = {
                                "formula": row["formula"], "weight": 1.0,
                                "direction": 1 if row["ic"] > 0 else -1,
                            }
                            st.rerun()

        with right_col:
            st.subheader(f"已选因子 ({len(st.session_state.selected_factors)})")
            if st.session_state.selected_factors:
                for name in st.session_state.selected_factors:
                    st.text(f"• {name[:30]}")
            else:
                st.caption("尚未选择")

# ===== TAB 2: 策略构建 =====
with tab2:
    st.header("策略构建")

    if not st.session_state.selected_factors:
        st.info("请先在因子扫描页选择因子")
    else:
        st.subheader(f"已选 {len(st.session_state.selected_factors)} 个因子")

        for idx, (fname, finfo) in enumerate(list(st.session_state.selected_factors.items())):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.text(fname[:60])
            with c2:
                w = st.number_input("权重", 0.0, 10.0, finfo["weight"], 0.1, key=f"w_{idx}")
                st.session_state.selected_factors[fname]["weight"] = w
            with c3:
                if st.button("删除", key=f"del_{idx}"):
                    st.session_state.selected_factors.pop(fname)
                    st.rerun()

        st.divider()
        st.caption("策略公式预览: 默认对每个因子做 rank 截面标准化，然后加权合成再 rank 选 Top-N")

# ===== TAB 3: 组合输出 =====
with tab3:
    st.header("组合输出")

    if not st.session_state.selected_factors:
        st.info("请先在因子扫描页选择因子并构建策略")
    else:
        target_n = st.number_input("标的数量", 10, 200, 50, 10)
        rebalance = st.number_input("调仓频率 (交易日)", 1, 20, 1, 1, help="1=每日调仓, 3=每3天调一次")
        neutralize_out = st.selectbox("中性化", ["无", "市值", "行业", "行业+市值"],
                                       help="与IC扫描时一致的中性化处理")
        col1, col2 = st.columns(2)
        with col1:
            begin_date = st.text_input("起始日期", "20260501")
        with col2:
            end_date = st.text_input("结束日期", "20260531")

        if st.button("生成组合", type="primary"):
            factors = {k: v["formula"] for k, v in st.session_state.selected_factors.items()}
            weights = {k: v["weight"] for k, v in st.session_state.selected_factors.items()}
            directions = {k: v.get("direction", 1) for k, v in st.session_state.selected_factors.items()}

            neu_map = {"无": "", "市值": "size", "行业": "industry", "行业+市值": "both"}
            with st.spinner(f"生成 {begin_date}~{end_date} 组合..."):
                df = PortfolioOutput.generate_batch(
                    conn, factors, weights, directions, builder,
                    int(begin_date), int(end_date), target_n,
                    rebalance_days=rebalance, warmup=120,
                    neutralize=neu_map[neutralize_out],
                    progress_callback=lambda d: st.text(f"已完成 {d} 天"))

            if not df.empty:
                st.session_state.output_df = df
                st.success(f"完成! {df['trade_date'].nunique()} 天, {len(df)} 行")
                st.dataframe(df.head(20), use_container_width=True)

                # Download
                csv = df.to_csv(index=False)
                st.download_button("下载 CSV", csv, f"portfolio_{begin_date}_{end_date}.csv", "text/csv")
            else:
                st.error("生成失败，请检查日期范围是否有数据")
