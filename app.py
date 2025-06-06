import streamlit as st
from dotenv import load_dotenv
load_dotenv() 
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import os
import json

class minone: 
    def __init__(self,user,content,location,date):
        self.user = user    
        self.content = content   
        self.location = location  
        self.date = date     
    def __str__(self):
        return f"작성자: {self.user}, 내용: {self.content}, 위치: {self.location}, 날짜: {self.date}"

def get_gs():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.getenv("GSPREAD_SERVICE_ACCOUNT")
    if creds_json_str is None:
        st.error("GSPREAD_SERVICE_ACCOUNT 환경 변수를 설정해주세요!")
        st.stop()
    creds_dict = json.loads(creds_json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data
def load_data(_client):
    sheet = _client.open("social-problem").worksheet("Sheet1") 
    all_values = sheet.get_all_values() 

    if len(all_values) > 1:
            headers = all_values[0]
            data = all_values[1:]
            df = pd.DataFrame(data, columns=headers)
            df['Latitude'] = pd.to_numeric(df['Latitude'])
            df['Longitude'] = pd.to_numeric(df['Longitude'])
    else:
            df = pd.DataFrame(columns=["User", "Content", "Latitude", "Longitude", "Date"])
    return df


st.set_page_config(page_title="민원 신고 앱", layout="wide")
st.title("민원 신고 앱")


gs_client = get_gs()
if gs_client:
    df_minone = load_data(gs_client)
else:
    st.error("Google Sheets 연동에 실패")
    st.stop()


col1, col2 = st.columns([0.6, 0.4]) 

with col1:
    st.subheader("민원 발생 위치 선택")
    yonsei= [37.5659, 126.9384]
    m = folium.Map(location=yonsei, zoom_start=16)
    
    for idx, row in df_minone.iterrows():
        popup_text = f"{row['User']}: {row['Content'][:30]}..."
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            tooltip=row["User"],
            popup=popup_text,
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 지도 클릭 시 좌표를 얻기 위한 기능 추가
    m.add_child(folium.ClickForMarker())
    map_info = st_folium(m, use_container_width=True,height=500)

    # 마지막으로 클릭한 좌표 저장 
    clicked_jwapyo = None
    if map_info and map_info.get("last_clicked"):
        lat, lon = map_info["last_clicked"]["lat"], map_info["last_clicked"]["lng"]
        clicked_jwapyo = (lat, lon)
        st.write(f"선택된 위치: 위도 `{lat:.5f}`, 경도 `{lon:.5f}` ")
      


with col2:
    st.subheader("민원 내용 작성")
    if map_info and map_info.get("last_clicked"):
            st.write(":red[위치가 선택이 되었으니 민원을 작성하세요]")
    with st.form(key="minone_form", clear_on_submit=True):
        user_name = st.text_input("작성자 이름") 
        minone_content = st.text_area("민원 상세 내용") 
        date = st.date_input("작성 날짜", value=datetime.date.today()) 
        submit_btn = st.form_submit_button("민원 제출")

    if submit_btn:
        # 유효성 검사
        if not clicked_jwapyo:
            st.error("지도에서 민원 위치를 먼저 선택해주세요.")
        elif not user_name or not minone_content:
            st.error("작성자와 민원 내용을 모두 입력해주세요.") 
        else:
            new_minone = minone(user_name,minone_content, clicked_jwapyo, str(date))
            
            try:
                sheet = gs_client.open("social-problem").worksheet("Sheet1")
                new_row = [new_minone.user, new_minone.content, new_minone.location[0], new_minone.location[1], new_minone.date]
                sheet.append_row(new_row) 
                
                st.success("새로운 민원이 성공적으로 등록되었습니다.") 
                st.write(str(new_minone)) 
                
                st.cache_data.clear()
            except Exception as e:
                st.error(f"구글시트트 저장에 실패: {e}")

st.divider()
st.subheader("접수된 민원 현황 조회")

if df_minone.empty:
    st.warning("아직 접수된 민원이 없습니다다.")
else:
    tab1, tab2, tab3 = st.tabs(["모든 민원 ","작성자별 조회", "날짜별 통계"])
    with tab1:
        st.write("모든 민원을 정리합니다.")
        st.dataframe(df_minone)

    with tab2:
        st.write("특정 작성자의 민원을 검색합니다.")
        search_user = st.text_input("조회할 작성자 이름 입력", key="search_input")
        if search_user:
            find_df = df_minone[df_minone["User"].str.lower() == search_user.lower()]
            count = len(find_df)
            st.write(f"'{search_user}' 님의 민원 목록 (총 {count} 건)")
            if count > 0:
                st.dataframe(find_df[['User', 'Content', 'Date']]) 
            else:
                st.info("해당 작성자의 민원이 없습니다.")
    with tab3:
        st.write(" 날짜별 민원 접수 건수")
        try:
            # 날짜 데이터를 datetime 객체로 변환
            df_minone["Date_obj"] = pd.to_datetime(df_minone["Date"], errors='coerce').dt.date
            df_minone.dropna(subset=['Date_obj'], inplace=True) 
            date_counts = df_minone.groupby("Date_obj").size()
            date_counts = date_counts.sort_index()
            st.bar_chart(date_counts)
            
        except Exception as e:
            st.error(f"차트 생성 중 오류 발생: {e}")