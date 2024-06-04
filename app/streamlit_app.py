import os
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static
import json


# セッション状態の初期化
if 'show_all' not in st.session_state:
    st.session_state['show_all'] = False  # 初期状態は地図上の物件のみを表示

# 地図上以外の物件も表示するボタンの状態を切り替える関数
def toggle_show_all():
    st.session_state['show_all'] = not st.session_state['show_all']

# Streamlit_Shere_Sercret環境変数から認証情報を取得
SPREADSHEET_ID = st.secrets["SPREADSHEET"]["ID"]
SERVICE_ACCOUNT_INFO = st.secrets["SERVICE_ACCOUNT"]
SP_SHEET = 'シート1'  # シート名

# スプレッドシートからデータを読み込む関数
def load_data_from_spreadsheet():
    # googleスプレッドシートの認証 jsonファイル読み込み(key値はGCPから取得)
    SP_CREDENTIAL_FILE = SERVICE_ACCOUNT_INFO
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials = Credentials.from_service_account_info(
        SP_CREDENTIAL_FILE,
        scopes=scopes
    )
    gc = gspread.authorize(credentials)

    SP_SHEET_KEY = SPREADSHEET_ID # d/〇〇/edit の〇〇部分
    sh  = gc.open_by_key(SP_SHEET_KEY)

    # 物件データの読み込み
    sh = gc.open_by_key(SPREADSHEET_ID)
    property_worksheet = sh.worksheet('シート1')  # 物件情報シート
    property_data = property_worksheet.get_all_values()
    property_df = pd.DataFrame(property_data[1:], columns=property_data[0])

    # フィットネスクラブデータの読み込み
    club_worksheet = sh.worksheet('フィットネスクラブ')  # フィットネスクラブ情報シート
    club_data = club_worksheet.get_all_values()
    club_df = pd.DataFrame(club_data[1:], columns=club_data[0])

    # データフレームのデータ型の確認と前処理（NaN値の除去など）
    property_df['latitude'] = pd.to_numeric(property_df['latitude'], errors='coerce')
    property_df['longitude'] = pd.to_numeric(property_df['longitude'], errors='coerce')
    property_df.dropna(subset=['latitude', 'longitude'], inplace=True)

    club_df['緯度'] = pd.to_numeric(club_df['緯度'], errors='coerce')
    club_df['経度'] = pd.to_numeric(club_df['経度'], errors='coerce')
    club_df.dropna(subset=['緯度', '経度'], inplace=True)

    return property_df, club_df



# データフレームの前処理を行う関数
def preprocess_dataframe(df):
    # '家賃' 列を浮動小数点数に変換し、NaN値を取り除く
    df['家賃'] = pd.to_numeric(df['家賃'], errors='coerce')
    df = df.dropna(subset=['家賃'])
    return df

def make_clickable(url, name):
    return f'<a target="_blank" href="{url}">{name}</a>'

# 地図を作成し、マーカーを追加する関数
def create_map(property_df, club_df):
    # 地図の中心を求める（物件の位置を基準にします）
    map_center = [property_df['latitude'].mean(), property_df['longitude'].mean()]
    m = folium.Map(location=map_center, zoom_start=12)

    # 物件マーカーの追加
    for idx, row in property_df.iterrows():
        if pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
            popup_html = f"""
            <b>名称:</b> {row['名称']}<br>
            <b>家賃:</b> {row['家賃']}万円<br>
            """
            popup = folium.Popup(popup_html, max_width=300)
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=popup,
                icon=folium.Icon(color='red')
            ).add_to(m)

    # フィットネスクラブのマーカー追加
    for idx, row in club_df.iterrows():
        if pd.notnull(row['緯度']) and pd.notnull(row['経度']):
            club_popup_html = f"""
            <b>名称:</b> {row['名称']}<br>
            <b>営業時間:</b> {row['営業時間']}<br>
            <b>月会費:</b> {row['月会費']}円<br>
            """
            club_popup = folium.Popup(club_popup_html, max_width=300)
            folium.Marker(
                [row['緯度'], row['経度']],
                popup=club_popup,
                icon=folium.Icon(color='blue')
            ).add_to(m)

    return m


# 検索結果を表示する関数
def display_search_results(filtered_df):
    # 物件番号を含む新しい列を作成
    filtered_df['物件番号'] = range(1, len(filtered_df) + 1)
    filtered_df['物件詳細URL'] = filtered_df['物件詳細URL'].apply(lambda x: make_clickable(x, "リンク"))
    display_columns = ['物件番号', '名称', 'アドレス', '階数', '家賃', '間取り', '物件詳細URL']
    filtered_df_display = filtered_df[display_columns]
    st.markdown(filtered_df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# メインのアプリケーション
# メインのアプリケーション
def main():
    property_df, club_df = load_data_from_spreadsheet()  # 両方のデータフレームを取得
    property_df = preprocess_dataframe(property_df)  # 物件データの前処理

    st.image('app/img.png')

    # StreamlitのUI要素（スライダー、ボタンなど）の各表示設定
    st.title(':blue[smart] :green[FIT] :blue[&] :orange[HOUSE]')

    # エリアと家賃フィルタバーを1:2の割合で分割
    col1, col2 = st.columns([1, 2])

    with col1:
        # エリア選択
        area = st.radio('■ エリア選択', property_df['区'].unique())

    with col2:
        # 家賃範囲選択のスライダーをfloat型で設定し、小数点第一位まで表示
        price_min, price_max = st.slider(
            '■ 家賃範囲 (万円)', 
            min_value=float(property_df['家賃'].min()), 
            max_value=float(property_df['家賃'].max()),
            value=(float(property_df['家賃'].min()), float(property_df['家賃'].max())),
            step=0.1,  # ステップサイズを0.1に設定
            format='%.1f'
        )

    with col2:
        # 間取り選択のデフォルト値をすべてに設定
        type_options = st.multiselect('■ 間取り選択', property_df['間取り'].unique(), default=property_df['間取り'].unique())

    # フィルタリング/ フィルタリングされたデータフレームの件数を取得
    filtered_df = property_df[(property_df['区'].isin([area])) & (property_df['間取り'].isin(type_options))]
    filtered_df = filtered_df[(filtered_df['家賃'] >= price_min) & (filtered_df['家賃'] <= price_max)]
    filtered_count = len(filtered_df)

    # 検索ボタン
    if st.button('検索＆更新'):
        st.write(f"物件検索数: {filtered_count}件 / 全{len(property_df)}件")
        display_search_results(filtered_df)  # 物件情報を表示
        m = create_map(filtered_df, club_df)
        folium_static(m)

        # フィットネスクラブの情報を表で表示
        st.subheader("フィットネスクラブ情報")
        st.dataframe(club_df)  # フィットネスクラブのデータフレームを表示

# アプリケーションの実行
if __name__ == "__main__":
    if 'search_clicked' not in st.session_state:
        st.session_state['search_clicked'] = False
    if 'show_all' not in st.session_state:
        st.session_state['show_all'] = False
    main()
