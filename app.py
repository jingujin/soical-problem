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
        return f"{self.user},{self.content},{self.location},{self.date}"

def get_gs():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # 환경 변수에서 JSON 인증 정보 문자열을 가져옴
    creds_json_str = os.getenv("GSPREAD_SERVICE_ACCOUNT")
    if creds_json_str is None:
        st.error("GSPREAD_SERVICE_ACCOUNT 환경 변수를 설정해주세요!")
        st.stop()
    
    # JSON 문자열을 딕셔너리로 변환
    creds_dict = json.loads(creds_json_str)
    
    # 딕셔너리를 사용해 인증
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data
def load_data_from_sheet(_client):
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


gspread_client = get_gs()
if gspread_client:
    df_minone = load_data_from_sheet(gspread_client)
else:
    st.error("Google Sheets 연동에 실패")
    st.stop()


col1, col2 = st.columns([0.6, 0.4]) # 화면을 6:4 비율로 나눔

with col1:
    st.subheader("민원 발생 위치 선택")
    map_center = [37.5665, 126.9780]
    m = folium.Map(location=map_center, zoom_start=20)
    
    # 기존 민원들을 지도에 마커로 표시 
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

    # Streamlit에 지도 렌더링
    map_data = st_folium(m, use_container_width=True)

    # 마지막으로 클릭한 좌표 저장 
    clicked_coords = None
    if map_data and map_data.get("last_clicked"):
        lat, lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        clicked_coords = (lat, lon)
        st.write(f"선택된 위치: 위도 `{lat:.5f}`, 경도 `{lon:.5f}`")


with col2:
    #  민원 입력 폼 영역 
    st.subheader("민원 내용 작성")
    with st.form(key="minone_form", clear_on_submit=True):
        author = st.text_input("작성자 이름") 
        content = st.text_area("민원 상세 내용") 
        date = st.date_input("작성 날짜", value=datetime.date.today()) 
        menu= ['기물/기자재','교통', '아파트' , '쓰레기', '주정차 단속', '치안']
        type = st.sidebar.selectbox("민원 분류", menu) 

        
        submit_button = st.form_submit_button("민원 제출")

    if submit_button:
        # 유효성 검사
        if not clicked_coords:
            st.error("지도에서 민원 위치를 먼저 선택해주세요.") 
        elif not author or not content:
            st.error("작성자와 민원 내용을 모두 입력해주세요.") 
        else:
            new_minone = minone(author, content, clicked_coords, str(date))
            
            try:
                sheet = gspread_client.open("social-problem").worksheet("Sheet1")
                row_to_add = [new_minone.user, new_minone.content, new_minone.location[0], new_minone.location[1], new_minone.date]
                sheet.append_row(row_to_add) 
                
                st.success("새로운 민원이 성공적으로 등록되었습니다.") 
                st.write(str(new_minone)) 
                
                # 데이터 캐시를 초기화하여 즉시 변경사항을 반영
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Google Sheets 저장에 실패했습니다: {e}")
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