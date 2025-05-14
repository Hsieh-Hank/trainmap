import requests
import json
import time
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import folium
from folium.plugins import MarkerCluster

# 配置常數
APP_ID = '111b15005-7c56966a-0b50-4c94'
APP_KEY = 'f9292938-f166-4570-8f43-3f1d96d97b60'
AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TRAIN_API_URL = "https://tdx.transportdata.tw/api/basic/v3/Rail/TRA/TrainLiveBoard?%24top=100&%24format=JSON"
STATION_API_URL = "https://tdx.transportdata.tw/api/basic/v3/Rail/TRA/Station?%24format=JSON"
class Auth:
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key
        self._token = None
        self._token_expires_at = 0

    def get_auth_header(self):
        return {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

    def get_access_token(self):
        current_time = time.time()
        if self._token and current_time < self._token_expires_at:
            return self._token
        try:
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.app_id,
                'client_secret': self.app_key
            }
            response = requests.post(AUTH_URL, headers=self.get_auth_header(), data=data)
            response.raise_for_status()
            auth_data = response.json()
            self._token = auth_data.get('access_token')
            self._token_expires_at = current_time + auth_data.get('expires_in', 3600) - 60
            return self._token
        except requests.exceptions.RequestException as e:
            print(f"Error getting access token: {e}")
            raise

def fetch_train_data(auth):
    token = auth.get_access_token()
    headers = {
        'authorization': f'Bearer {token}',
        'Accept-Encoding': 'gzip'
    }
    r = requests.get(TRAIN_API_URL, headers=headers)
    r.raise_for_status()
    return r.json()

def fetch_station_data(auth):
    token = auth.get_access_token()
    headers = {
        'authorization': f'Bearer {token}',
        'Accept-Encoding': 'gzip'
    }
    r = requests.get(STATION_API_URL, headers=headers)
    r.raise_for_status()
    return r.json()

def create_app():
    app = dash.Dash(__name__)
    auth = Auth(APP_ID, APP_KEY)

    app.layout = html.Div([
        html.H1('台鐵動態地圖', className='header'),
        html.Iframe(id='live-update-map', srcDoc=None, width='100%', height='1080'),
        dcc.Interval(
            id='interval-component',
            interval=2*60*1000,
            n_intervals=0
        )
    ])

    @app.callback(
        Output('live-update-map', 'srcDoc'),
        Input('interval-component', 'n_intervals')
    )
    def update_graph_live(n):
        try:
            train_data = fetch_train_data(auth)
            station_data = fetch_station_data(auth)

            train_df = pd.DataFrame(train_data.get("TrainLiveBoards", []))
            station_df = pd.DataFrame(station_data.get("Stations", []))

            station_df["StationNameZh"] = station_df["StationName"].apply(lambda x: x.get("Zh_tw") if x else None)
            station_df["PositionLat"] = station_df["StationPosition"].apply(lambda x: x.get("PositionLat") if x else None)
            station_df["PositionLon"] = station_df["StationPosition"].apply(lambda x: x.get("PositionLon") if x else None)

            # 合併
            merged_df = pd.merge(train_df, station_df, on="StationID", how="left")

            # 創建地圖
            m = folium.Map(location=[23.5, 121], tiles="Cartodb dark_matter", zoom_start=7)
            marker_cluster = MarkerCluster().add_to(m)

            # 添加標記
            for idx, row in merged_df.iterrows():
                popup_content = f"""
                <div style="width: 300px; font-size: 16px;">
                    <b>站名:</b> {row['StationNameZh']}<br>
                    <b>延遲時間:</b> {row['DelayTime']}<br>
                    <b>列車號碼:</b> {row['TrainNo']}
                </div>
                """
                folium.Marker(
                    location=[row['PositionLat'], row['PositionLon']],
                    popup=folium.Popup(popup_content, max_width=400),
                    icon=folium.Icon(color='blue' if row['DelayTime'] <= 5 else 'red')
                ).add_to(marker_cluster)

            # 將地圖保存為 HTML 字串
            return m._repr_html_()

        except Exception as e:
            print(f"Error updating map: {e}")
            return f"<div>無法更新地圖: {str(e)}</div>"

    return app

if __name__ == '__main__':
    app = create_app()
    app.run_server(debug=True)