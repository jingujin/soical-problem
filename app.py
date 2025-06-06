import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import datetime
import os
import json
import io
from pathlib import Path
import altair as alt


load_dotenv()  

class minone:  
    def __init__(self,user,content,location,date,minone_type): 
        self.user = user      
        self.content = content    
        self.location = location  
        self.date = date  
        self.complaint_type = minone_type    
    def __str__(self): 
        return f"작성자: {self.user}, 내용: {self.content}, 위치: {self.location}, 날짜: {self.date}" 

def get_gs(): 
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"] 
    key_path_from_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not key_path_from_env:
            st.error("GOOGLE_APPLICATION_CREDENTIALS 환경 변수를 찾을 수 없습니다. .env 파일의 내용을 확인해주세요.")
            st.stop()    
    full_key_path = Path(__file__).parent / key_path_from_env

    creds = Credentials.from_service_account_file(
            full_key_path,
            scopes=scope
        )    
    gs_client = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return gs_client, drive_service
    
def upload_image(drive_service, image_file, folder_id):
    try:
        image_byte = image_file.getvalue()
        files = io.BytesIO(image_byte)

        file_metadata = {
            'name': image_file.name,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(files, mimetype=image_file.type, resumable=True)
        
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        file_id = file.get('id')
        drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        
        return f"https://drive.google.com/thumbnail?id={file_id}"
    except Exception as e:
        st.error(f"이미지 업로드 실패: {e}")
        return None



@st.cache_data(ttl=300) 
def load_data(_client): 
    try:
        sheet = _client.open("social-problem").worksheet("Sheet1")  
        all_values = sheet.get_all_values()  

        if len(all_values) > 1: 
            headers = all_values[0] 
            data = all_values[1:] 
            df = pd.DataFrame(data, columns=headers) 
            df['Latitude'] = pd.to_numeric(df['Latitude']) 
            df['Longitude'] = pd.to_numeric(df['Longitude']) 
        else: 
            df = pd.DataFrame(columns=["User", "Content", "Latitude", "Longitude", "Date","Type","ImageURL"]) 
        return df 
    except APIError as e:
        st.cache_data.clear()
        st.error(f"데이터 로딩 실패 (API 오류): {e}. Google API 할당량 초과일 수 있으니, 잠시 후 새로고침해주세요.")
        st.stop()
    except Exception as e:
        st.cache_data.clear()
        st.error(f"데이터 로딩 중 알 수 없는 오류 발생: {e}")
        st.stop()


st.set_page_config(page_title="민원 신고 앱", layout="wide") 
st.title("민원 신고 앱") 


gs_client, drive_service = get_gs()
df_minone = load_data(gs_client)
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
if 'clicked_location' not in st.session_state:
    st.session_state.clicked_location = None

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

        m.add_child(folium.ClickForMarker()) 
        map_info = st_folium(m, use_container_width=True,height=500) 

        if map_info and map_info.get("last_clicked"): 
            lat, lon = map_info["last_clicked"]["lat"], map_info["last_clicked"]["lng"] 
            st.session_state.clicked_location = (lat, lon)
            st.write(f"선택된 위치: 위도 `{lat:.5f}`, 경도 `{lon:.5f}` ") 
        
with col2: 
        st.subheader("민원 내용 작성") 
        if st.session_state.clicked_location:
            st.write(":red[위치가 선택이 되었으니 민원을 작성하세요]") 
        with st.form(key="minone_form", clear_on_submit=True): 
            menu= ['기물/기자재','교통', '아파트' , '쓰레기', '주정차 단속', '치안','기타'] 
            minone_type = st.selectbox("민원 분류", menu,index=None, placeholder="민원 유형을 선택하세요...")  
            user_name = st.text_input("작성자 이름")  
            minone_content = st.text_area("민원 상세 내용")  
            date = st.date_input("작성 날짜", value=datetime.date.today())  

            img_file = st.file_uploader('이미지 업로드 (선택 사항)', type=['png', 'jpg', 'jpeg'])
            submit_btn = st.form_submit_button("민원 제출") 
        if submit_btn: 
            if st.session_state.clicked_location is None:
                st.error("지도에서 민원 위치를 먼저 선택해주세요.")
            elif not all([user_name, minone_content, minone_type]):
                st.error("민원 분류, 작성자 이름, 상세 내용을 모두 입력해주세요.")
            else:
                with st.spinner("민원을 등록하는 중입니다..."):
                    image_url = ""
                    if img_file is not None:
                        if not GDRIVE_FOLDER_ID:
                            st.error("GDRIVE_FOLDER_ID 환경 변수가 설정되지 않아 이미지를 업로드할 수 없습니다.")
                            st.stop()
                        image_url = upload_image(drive_service, img_file, GDRIVE_FOLDER_ID)
                    try: 
                        new_row = [
                        user_name, minone_content,
                        st.session_state.clicked_location[0], st.session_state.clicked_location[1],
                        str(datetime.date.today()), minone_type, image_url
                    ]          
                        sheet = gs_client.open("social-problem").worksheet("Sheet1") 
                        sheet.append_row(new_row)  
                        st.success("새로운 민원이 성공적으로 등록되었습니다.")  
                        st.cache_data.clear() 
                        st.rerun() 
                    except Exception as e: 
                        st.error(f"구글시트트 저장에 실패: {e}") 

st.divider()
st.subheader("접수된 민원 현황 조회") 

if df_minone.empty:
    st.warning("아직 접수된 민원이 없습니다.")
else:
    tab1, tab2, tab3 = st.tabs(["전체 민원 보기", "작성자별 조회", "날짜별 통계"])

with tab1:
    st.write(f"#### 총 {len(df_minone)}건의 민원 목록")
    df_minone = df_minone.reset_index()  # 기존 인덱스(입력 순서) 보존
    sorted_df = df_minone.sort_values(by=['Date', 'index'], ascending=[True, True])
    for idx, row in sorted_df.iterrows():
        with st.expander(f"**{row.get('Date', 'N/A')} / {row.get('Type', 'N/A')} / {row.get('User', 'N/A')}**"):
            st.markdown(f"**내용:** {row.get('Content', 'N/A')}")
            image_url = str(row.get('ImageURL', '') or '')
            if pd.isna(image_url):
                image_url = ''
            else:
                image_url = str(image_url).strip().replace('’', '').replace('‘', '').replace('"', '').replace("'", "")

            if image_url.startswith('http'):
                st.image(image_url, caption="첨부 이미지", width=300)





    
with tab2:
    st.write("#### 특정 작성자의 민원을 검색합니다.")
    search_user = st.text_input("조회할 작성자 이름 입력", key="search_user_input")
    if search_user:
        find_df = df_minone[df_minone["User"].str.contains(search_user, case=False, na=False)]
        count = len(find_df)
        st.write(f"**'{search_user}'** 님으로 검색된 민원 (총 {count} 건)")
        for idx, row in find_df.iterrows():
            with st.expander(f"{row.get('Date', 'N/A')} / {row.get('Type', 'N/A')} / {row.get('User', 'N/A')}"):
                st.markdown(f"**내용:** {row.get('Content', 'N/A')}")
                image_url = str(row.get('ImageURL', '') or '').strip()
                if image_url.startswith('http'):
                    st.image(image_url, caption="첨부 이미지", width=300)
                else:
                    st.write("이미지 없음")



with tab3:
    st.write("#### 날짜별 민원 접수 건수")
    try:
        df_chart = df_minone.copy()
        df_chart['Date'] = pd.to_datetime(df_chart['Date'], errors='coerce').dt.date
        df_chart.dropna(subset=['Date'], inplace=True)
        date_counts = df_chart['Date'].value_counts().sort_index()
        if not date_counts.empty:
            date_range = pd.date_range(start=date_counts.index.min(), end=date_counts.index.max())
            date_labels = date_range.strftime('%Y-%m-%d')
            df_all = pd.DataFrame({'Date': date_labels})
            df_all['count'] = df_all['Date'].map(date_counts.rename(lambda x: x.strftime('%Y-%m-%d'))).fillna(0).astype(int)
        else:
            df_all = pd.DataFrame(columns=['Date', 'count'])
        chart = alt.Chart(df_all).mark_bar().encode(
            x=alt.X('Date:N', axis=alt.Axis(title='날짜')),
            y=alt.Y('count:Q', title='민원 접수 건수')
        ).properties(width=700, height=400)
        st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.error(f"차트 생성 중 오류가 발생했습니다: {e}")
