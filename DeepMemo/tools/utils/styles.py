import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    /* ============================================================================
       全局样式 - Apple 设计系统
       ============================================================================ */
    
    /* 应用容器 */
    .stApp {
        background-color: #f5f5f7;
        font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
        color: #1d1d1f;
    }
    
    /* 隐藏 Streamlit 默认元素 */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    
    /* ============================================================================
       排版系统
       ============================================================================ */
    
    h1, h2, h3, h4, h5, h6 {
        color: #1d1d1f;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    h1 {
        font-size: 32px;
        line-height: 1.2;
        margin-bottom: 16px;
    }
    
    h2 {
        font-size: 24px;
        line-height: 1.3;
        margin-bottom: 12px;
    }
    
    h3 {
        font-size: 18px;
        line-height: 1.4;
        margin-bottom: 8px;
    }
    
    p, span, div {
        font-size: 16px;
        line-height: 1.5;
        color: #1d1d1f;
    }
    
    .stCaption {
        font-size: 13px;
        color: #86868b;
    }
    
    /* ============================================================================
       容器 - Card 风格
       ============================================================================ */
    
    div[data-testid="stVerticalBlockBorderWrapper"],
    .stContainer {
        background-color: white;
        border-radius: 18px;
        border: none;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        padding: 20px;
        margin-bottom: 12px;
        transition: box-shadow 0.2s ease;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"]:hover,
    .stContainer:hover {
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
    }
    
    /* ============================================================================
       按钮 - iOS 风格
       ============================================================================ */
    
    .stButton > button {
        background-color: #f5f5f7 !important;
        color: #1d1d1f !important;
        border: none !important;
        border-radius: 12px !important;
        height: 44px;
        font-size: 16px;
        font-weight: 500;
        transition: all 0.2s ease;
        cursor: pointer;
        padding: 0 20px;
    }
    
    .stButton > button:hover:not(:disabled) {
        background-color: #e8e8eb !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    
    .stButton > button:active:not(:disabled) {
        background-color: #d8d8db !important;
    }
    
    /* Primary 按钮 */
    .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #0071e3 !important;
        color: white !important;
    }
    
    .stButton > button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
        background-color: #0077ed !important;
        box-shadow: 0 4px 12px rgba(0, 113, 227, 0.3);
    }
    
    .stButton > button:disabled {
        background-color: #f5f5f7 !important;
        color: #d2d2d7 !important;
        cursor: not-allowed;
    }
    
    /* ============================================================================
       输入框 - 极简风格
       ============================================================================ */
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {
        background-color: white !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 10px !important;
        color: #1d1d1f !important;
        font-size: 16px;
        padding: 12px 16px;
        transition: all 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.1) !important;
        outline: none;
    }
    
    /* ============================================================================
       Radio & Checkbox
       ============================================================================ */
    
    .stRadio > div > label > div:first-child,
    .stCheckbox > div > label > div:first-child {
        background-color: white;
        border: 2px solid #d2d2d7;
        border-radius: 8px;
        width: 20px;
        height: 20px;
    }
    
    .stRadio > div > label > div:first-child.checked,
    .stCheckbox > div > label > div:first-child.checked {
        background-color: #0071e3;
        border-color: #0071e3;
    }
    
    /* ============================================================================
       侧边栏 - 极简导航
       ============================================================================ */
    
    .stSidebar {
        background-color: white;
        border-right: 1px solid #d2d2d7;
    }
    
    .stSidebar .stRadio > div > label {
        padding: 12px 16px;
        margin-bottom: 4px;
        border-radius: 10px;
        transition: background-color 0.2s ease;
    }
    
    .stSidebar .stRadio > div > label:hover {
        background-color: #f5f5f7;
    }
    
    .stSidebar .stRadio > div > div > label[data-baseweb="radio"] {
        padding: 12px 16px;
        border-radius: 10px;
        background-color: transparent;
    }
    
    /* 侧边栏标题 */
    .stSidebar h1, .stSidebar h2, .stSidebar h3 {
        font-size: 18px;
        margin: 20px 16px 12px;
        padding: 0;
    }
    
    /* ============================================================================
       进度条 - 优雅设计
       ============================================================================ */
    
    .stProgress > div > div > div {
        background-color: #0071e3;
        border-radius: 4px;
    }
    
    .stProgress > div > div {
        background-color: #f5f5f7;
        border-radius: 4px;
    }
    
    /* ============================================================================
       提示框 (Info, Success, Warning, Error)
       ============================================================================ */
    
    div[data-testid="stAlert"] {
        border-radius: 12px;
        border: none;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    div[data-testid="stAlert"] > div:first-child {
        font-weight: 500;
    }
    
    /* ============================================================================
       分割线
       ============================================================================ */
    
    .stDivider {
        margin: 20px 0;
        border-top: 1px solid #d2d2d7;
    }
    
    /* ============================================================================
       表格
       ============================================================================ */
    
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    
    .stDataFrame td, .stDataFrame th {
        padding: 12px 16px;
        border-color: #d2d2d7;
    }
    
    /* ============================================================================
       Metric 指标卡
       ============================================================================ */
    
    div[data-testid="metric-container"] {
        background-color: white;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #d2d2d7;
    }
    
    </style>
    """, unsafe_allow_html=True)