
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

def get_gspread_client():
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
            # 데이터가 없을 경우, 정해진 컬럼을 가진 빈 DataFrame을 생성합니다.
            df = pd.DataFrame(columns=["User", "Content", "Latitude", "Longitude", "Date"])
    return df

