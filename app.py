
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

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
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope) 
    return gspread.authorize(creds)

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




