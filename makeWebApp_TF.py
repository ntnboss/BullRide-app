import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. 페이지 기본 설정 ---
st.set_page_config(
    page_title="추세추종 종목 발굴기 Pro",
    page_icon="🚀",
    layout="wide"
)

# --- 2. 데이터 분석 함수 ---
@st.cache_data(ttl=3600)
def get_candidates(market, limit=30):
    """ 시장별 유동성 상위 종목 가져오기 """
    df_krx = fdr.StockListing('KRX')
    
    # 전처리 (콤마 제거 및 숫자 변환)
    cols = ['Marcap', 'Close', 'Amount']
    for col in cols:
        if col in df_krx.columns and df_krx[col].dtype == 'object':
            df_krx[col] = df_krx[col].astype(str).str.replace(',', '')
            df_krx[col] = pd.to_numeric(df_krx[col], errors='coerce')
            
    df_krx = df_krx.dropna(subset=['Marcap', 'Close'])
    
    if market == 'KOSPI':
        df = df_krx[df_krx['Market'] == 'KOSPI']
    elif market == 'KOSDAQ':
        df = df_krx[df_krx['Market'] == 'KOSDAQ']
        # 코스닥은 시총 500억 이상만 (너무 작은 종목 제외)
        df = df[df['Marcap'] >= 500_0000_0000]
    else: # NASDAQ
        # 나스닥은 전체 리스트가 너무 커서, 예제용으로 나스닥100(QQQ) 구성종목 등을 사용하는 게 현실적입니다.
        # 여기서는 fdr의 NASDAQ 리스트 중 상위 일부를 가져옵니다.
        df_nas = fdr.StockListing('NASDAQ')
        return df_nas.head(limit)[['Symbol', 'Name']].rename(columns={'Symbol':'Code'}).to_dict('records')

    # 거래대금(유동성) 상위 순 정렬
    df = df.sort_values(by='Amount', ascending=False)
    return df[['Code', 'Name']].head(limit).to_dict('records')

def analyze_stock(code, name, market):
    """ 개별 종목 정밀 분석 """
    try:
        # 1년치 데이터 (52주 신고가 계산용)
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        df = fdr.DataReader(code, start_date)
        
        if len(df) < 120: return None
        
        current_price = df['Close'].iloc[-1]
        
        # --- 지표 계산 ---
        # 1. 이동평균선
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        
        # 2. RSI
        delta = df['Close'].diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
        rsi = 100 if loss == 0 else 100 - (100 / (1 + (gain/loss)))
        
        # 3. 기울기 (20일선 상승 각도)
        ma20_prev = df['Close'].rolling(20).mean().iloc[-6] # 5일전
        slope = ((ma20 - ma20_prev) / ma20_prev) * 100
        
        # 4. 추세 진행률 (Position in 52-week range)
        low_52w = df['Low'].min()
        high_52w = df['High'].max()
        progress = ((current_price - low_52w) / (high_52w - low_52w))
        
        # --- 필터링 조건 (추세추종) ---
        # 정배열(20>60) + 현재가가 20일선 위에 있음
        if current_price > ma20 and ma20 > ma60:
            
            # 상태 판단
            status = ""
            if rsi >= 70: status = "🔥과열 (주의)"
            elif slope >= 3.0: status = "🚀강력 매수"
            elif slope >= 1.0: status = "✅매수 적기"
            else: status = "➡️관망/보유"
            
            return {
                '종목명': name,
                '현재가': current_price,
                '상태': status,
                '추세강도(기울기)': round(slope, 2), # 정렬 기준 1
                '진행률': progress, # 0.0 ~ 1.0
                'RSI': round(rsi, 1),
                '코드': code
            }
        return None
    except Exception as e:
        return None

# --- 3. UI 구성 ---
st.title("🚀 AI 추세추종 종목 발굴기 Pro")
st.markdown("""
**추세 강도가 높은 순서대로 정렬됩니다.**
- **추세강도(기울기):** 높을수록 주가가 가파르게 오르는 중입니다.
- **진행률:** 52주 최저가(0%) ~ 최고가(100%) 사이의 위치입니다.
""")

with st.sidebar:
    st.header("🔍 검색 설정")
    market_option = st.selectbox("시장 선택", ["KOSDAQ", "KOSPI", "NASDAQ"])
    scan_limit = st.slider("분석 종목 수 (거래량 상위)", 20, 200, 50)
    st.caption("※ 종목 수가 많으면 시간이 오래 걸립니다.")

if st.button("분석 시작 (Start)"):
    st.divider()
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    candidates = get_candidates(market_option, scan_limit)
    st.write(f"총 {len(candidates)}개 종목을 분석 중입니다...")
    
    results = []
    
    for i, stock in enumerate(candidates):
        # 진행률 표시
        prog_val = (i + 1) / len(candidates)
        progress_bar.progress(prog_val)
        status_text.text(f"분석 중.. {stock['Name']}")
        
        # 분석 수행
        res = analyze_stock(stock['Code'], stock['Name'], market_option)
        if res:
            results.append(res)
            
    progress_bar.empty()
    status_text.empty()
    
    if results:
        # [핵심] 정렬 로직: 추세강도(기울기) 내림차순 -> 가장 센 놈이 맨 위로
        df_res = pd.DataFrame(results)
        df_res = df_res.sort_values(by='추세강도(기울기)', ascending=False)
        
        st.success(f"조건을 만족하는 {len(df_res)}개 종목 발견! (강도순 정렬)")
        
        # [핵심] 데이터프레임 시각화 설정 (게이지 바 적용)
        st.dataframe(
            df_res,
            column_config={
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "현재가": st.column_config.NumberColumn(format="%d원" if market_option != "NASDAQ" else "$%.2f"),
                "추세강도(기울기)": st.column_config.NumberColumn(format="%.2f%%"),
                "진행률": st.column_config.ProgressColumn(
                    "52주 위치 (진행률)",
                    help="최저가(0%) ~ 최고가(100%)",
                    format="%.0f%%",
                    min_value=0,
                    max_value=1,
                ),
                "RSI": st.column_config.NumberColumn(format="%.1f"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("조건에 맞는 종목이 없습니다. 하락장일 가능성이 높습니다.")