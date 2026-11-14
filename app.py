import calendar
from datetime import date, timedelta
import math
import re
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title='FarmShift | Crop Rotation Planner', page_icon='🌿', layout='wide', initial_sidebar_state='collapsed')
CROPS = {
 'Wheat': {'family':'Poaceae','min':8,'max':27,'water':330,'ph':(6.0,7.5),'ec':4.0,'months':5,'start':11},
 'Barley': {'family':'Poaceae','min':7,'max':29,'water':250,'ph':(6.0,8.0),'ec':6.0,'months':5,'start':11},
 'Lentil': {'family':'Fabaceae','min':9,'max':26,'water':220,'ph':(6.0,8.0),'ec':2.0,'months':4,'start':12},
 'Chickpea': {'family':'Fabaceae','min':12,'max':30,'water':240,'ph':(6.0,8.0),'ec':2.5,'months':4,'start':12},
 'Sorghum': {'family':'Poaceae','min':22,'max':36,'water':320,'ph':(5.5,8.5),'ec':4.0,'months':4,'start':5},
 'Sunflower': {'family':'Asteraceae','min':18,'max':33,'water':340,'ph':(6.0,7.8),'ec':3.0,'months':4,'start':3},
}
MONTHS = list(calendar.month_name)[1:]

def months_from(start, length):
    return [((start - 1 + i) % 12) + 1 for i in range(length)]

def season_years(end_year, start_month, length):
    # Season ends in the selected historical year if it crosses January.
    return end_year - (1 if start_month + length - 1 > 12 else 0), end_year

@st.cache_data(ttl=3600, show_spinner=False)
def nasa_monthly(lat, lon, start_year, end_year):
    url='https://power.larc.nasa.gov/api/temporal/monthly/point'
    params={'parameters':'T2M,PRECTOTCORR','community':'AG','longitude':lon,'latitude':lat,
            'start':start_year,'end':end_year,'format':'JSON'}
    response=requests.get(url,params=params,timeout=35)
    response.raise_for_status()
    raw=response.json()
    values=raw['properties']['parameter']
    rows=[]
    for key,t in values['T2M'].items():
        if len(key)!=6 or key[-2:]=='13':continue
        rain=values['PRECTOTCORR'].get(key)
        if t is None or rain is None or float(t)<=-900 or float(rain)<=-900:continue
        # NASA POWER monthly PRECTOTCORR is mm/day; convert to monthly total.
        y,m=int(key[:4]),int(key[4:])
        days=calendar.monthrange(y,m)[1]
        rows.append({'year':y,'month':m,'temperature_c':float(t),'rainfall_mm':float(rain)*days,'days':days})
    if not rows:raise ValueError('NASA returned no usable monthly observations for this location and period.')
    return pd.DataFrame(rows),response.url

def get_season(df, end_year, start_month, duration, explicit_start_year=None):
    start_year = explicit_start_year if explicit_start_year is not None else season_years(end_year,start_month,duration)[0]
    needed=[]
    for i in range(duration):
        n=start_month-1+i
        needed.append((start_year+n//12,n%12+1))
    part=df[df.apply(lambda r:(int(r.year),int(r.month)) in needed,axis=1)].copy()
    if len(part)!=duration:return None
    part['order']=part.apply(lambda r:needed.index((int(r.year),int(r.month))),axis=1)
    return part.sort_values('order')

def bound_score(value,low,high,soft=10):
    if low<=value<=high:return 100.0
    return max(0.0,100.0-abs(value-(low if value<low else high))*soft)

def crop_score(crop,season,water,soil,ph,ec):
    c=CROPS[crop]
    temp=float((season.temperature_c*season.days).sum()/season.days.sum())
    rain=float(season.rainfall_mm.sum())
    climate=bound_score(temp,c['min'],c['max'],7)
    # Water is a farmer-entered seasonal irrigation estimate in mm, not a measured source.
    available=rain+water
    water_score=min(100.0,100*available/c['water'])
    soil_score={'Loamy':92,'Sandy':75,'Clay':78,'Silty':85}.get(soil,80)
    if ph is not None:soil_score=.6*soil_score+.4*bound_score(ph,*c['ph'],soft=25)
    if ec is not None:soil_score=max(0,soil_score-max(0,ec-c['ec'])*14)
    return {'climate':round(climate,1),'water':round(water_score,1),'soil':round(soil_score,1),
            'temp':round(temp,1),'rain':round(rain,1),'water_need':c['water']}


st.markdown("""<style>
.stApp {background:#F8F7F2;color:#172D21} .block-container{max-width:1150px;padding-top:1.2rem;padding-bottom:3rem}
h1,h2,h3,p,label,[data-testid="stWidgetLabel"] p{color:#172D21!important}
[data-testid="stSidebar"]{background:#EAF1E5}
[data-testid="stSidebar"] *{color:#172D21!important}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-testid="stNumberInput"]>div>div{background:#DCEED5!important;border:1px solid #B7D1AE!important;border-radius:10px!important}
[data-baseweb="input"] input,[data-baseweb="select"] *,[data-testid="stNumberInput"] input{color:#101F16!important;-webkit-text-fill-color:#101F16!important;font-weight:600!important}
[data-testid="stNumberInput"] input{direction:ltr!important;text-align:left!important;font-family:Arial,sans-serif!important}
[data-testid="stSlider"] [role="slider"]{background:#37734F!important}
.stButton button[kind="primary"]{background:#276445!important;color:white!important;border-radius:11px!important;min-height:46px}
[data-testid="stDataFrame"]{background:white;border-radius:12px}
.hero{background:linear-gradient(110deg,#E2EDD9,#FCFAF2);border:1px solid #D4E4CF;border-radius:18px;padding:20px 26px;margin-bottom:18px}
.hero h1{margin:0;font-size:2rem;color:#18422D!important}.hero p{margin:6px 0 0;color:#465B49!important}
.smallnote{font-size:.86rem;color:#536653}.best{background:#E4F0DC;border-left:5px solid #2B6946;padding:12px 17px;border-radius:9px;margin:12px 0}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🌿 FarmShift</h1><p>Smarter crop rotations using real NASA climate observations.</p></div>',unsafe_allow_html=True)
if 'coords' not in st.session_state:st.session_state.coords=(28.445477,36.649388)
st.subheader('1 · Farm details')
with st.expander('📍 Select location on map (optional)',expanded=False):
    center=st.session_state.coords
    m=folium.Map(location=list(center),zoom_start=10,tiles='OpenStreetMap')
    folium.Marker(list(center),icon=folium.Icon(color='green')).add_to(m)
    clicked=st_folium(m,height=240,returned_objects=['last_clicked'],key='farm_map_simple')
    if clicked and clicked.get('last_clicked'):
        loc=clicked['last_clicked']; new=(round(loc['lat'],6),round(loc['lng'],6))
        if new!=st.session_state.coords:
            st.session_state.coords=new
            st.session_state.lat_input=f'{new[0]:.6f}'
            st.session_state.lon_input=f'{new[1]:.6f}'
            st.rerun()
    st.caption('If map tiles are unavailable, enter coordinates below.')
if 'lat_input' not in st.session_state:st.session_state.lat_input=f'{st.session_state.coords[0]:.6f}'
if 'lon_input' not in st.session_state:st.session_state.lon_input=f'{st.session_state.coords[1]:.6f}'
with st.form('one_page_inputs'):
    a,b,c=st.columns(3)
    with a:
        lat_text=st.text_input('Latitude (°) · English digits',key='lat_input')
        previous=st.selectbox('Previous crop',list(CROPS))
        year=st.selectbox('Historical season ending year',list(range(2025,2018,-1)))
    with b:
        lon_text=st.text_input('Longitude (°) · English digits',key='lon_input')
        soil=st.selectbox('Soil texture',['Loamy','Sandy','Clay','Silty'])
        start_name=st.selectbox('Planting month',MONTHS,index=10)
    with c:
        water=st.slider('Irrigation (mm per season)',0,800,275,25)
        priority=st.selectbox('Your priority',['Balanced','Water conservation','Soil health'])
        duration=st.slider('First crop duration (months)',2,8,5)
    submit=st.form_submit_button('🌿 Analyze farm',type='primary',use_container_width=True)
if submit:
    try:
        if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',lat_text.strip()) or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',lon_text.strip()):
            raise ValueError('Please enter coordinates with English digits (0–9).')
        lat,lon=float(lat_text),float(lon_text)
        if not(-90<=lat<=90 and -180<=lon<=180):raise ValueError('Coordinates are outside valid ranges.')
        st.session_state.coords=(lat,lon)
        st.session_state.analysis_params=dict(lat=lat,lon=lon,previous=previous,year=year,soil=soil,start=MONTHS.index(start_name)+1,water=water,priority=priority,duration=duration)
    except ValueError as e:st.error(str(e))
if 'analysis_params' in st.session_state:
    p=st.session_state.analysis_params
    st.subheader('2 · Your results')
    try:
        with st.spinner('Loading NASA POWER observations...'):
            df,source_url=nasa_monthly(p['lat'],p['lon'],p['year']-2,p['year']+1)
        season=get_season(df,p['year'],p['start'],p['duration'])
        if season is None:raise ValueError('Incomplete climate observations for the selected season.')
        mean_temp=float((season.temperature_c*season.days).sum()/season.days.sum())
        rain=float(season.rainfall_mm.sum())
        st.caption(f"NASA POWER historical observations · {p['lat']:.6f}, {p['lon']:.6f} · {calendar.month_name[p['start']]} planting · {p['year']} ending year")
        x,y=st.columns(2)
        x.metric('Season mean temperature',f'{mean_temp:.1f} °C')
        y.metric('Season rainfall',f'{rain:.1f} mm')
        rows=[]
        for first in CROPS:
            if first==p['previous']:continue
            first_stats=crop_score(first,season,p['water'],p['soil'],None,None)
            second_start=(p['start']-1+p['duration'])%12+1
            for second in CROPS:
                if second==first:continue
                second_duration=CROPS[second]['months']
                second_year=season_years(p['year'],p['start'],p['duration'])[0]+(p['start']-1+p['duration'])//12
                second_season=get_season(df,p['year'],second_start,second_duration,explicit_start_year=second_year)
                if second_season is None:continue
                second_stats=crop_score(second,second_season,p['water'],p['soil'],None,None)
                climate=(first_stats['climate']+second_stats['climate'])/2
                w=(first_stats['water']+second_stats['water'])/2
                s=(first_stats['soil']+second_stats['soil'])/2
                diversity=100 if CROPS[first]['family']!=CROPS[second]['family'] else 45
                bonus=10 if CROPS[p['previous']]['family']!=CROPS[first]['family'] else 0
                weights={'Balanced':(.35,.35,.2,.1),'Water conservation':(.25,.55,.1,.1),'Soil health':(.25,.2,.3,.25)}[p['priority']]
                score=sum(z*q for z,q in zip((climate,w,s,diversity),weights))+bonus*.5
                # Keep score uncapped until after ranking so saturated values do not conceal differences.
                rows.append(dict(rotation=f'{first} → {second}',score=score,climate=climate,water=w,soil=s,diversity=diversity,first=first,second=second,second_start=second_start,second_duration=second_duration,second_year=second_year,bonus=bonus))
        if not rows:raise ValueError('No complete crop rotations were found for this historical period.')
        ranked=sorted(rows,key=lambda r:(r['score'],r['water'],r['diversity']),reverse=True)[:3]
        best=ranked[0]
        st.markdown(f'<div class="best"><b>🌾 Best illustrative rotation: {best["rotation"]}</b><div>Plant {best["first"]} in {calendar.month_name[p["start"]]}, followed by {best["second"]} in {calendar.month_name[best["second_start"]]}.</div></div>',unsafe_allow_html=True)
        weights={'Balanced':(.35,.35,.2,.1),'Water conservation':(.25,.55,.1,.1),'Soil health':(.25,.2,.3,.25)}[p['priority']]
        table=[]
        for r in ranked:
            first_reduced=crop_score(r['first'],season,p['water']*.6,p['soil'],None,None)
            second_season=get_season(df,p['year'],r['second_start'],r['second_duration'],explicit_start_year=r['second_year'])
            second_reduced=crop_score(r['second'],second_season,p['water']*.6,p['soil'],None,None)
            reduced_water=(first_reduced['water']+second_reduced['water'])/2
            reduced_score=sum(z*q for z,q in zip((r['climate'],reduced_water,r['soil'],r['diversity']),weights))+r['bonus']*.5
            table.append({'Crop rotation':r['rotation'],'Score /100':round(min(100,r['score']),1),'Climate':round(r['climate'],1),'Water':round(r['water'],1),'Soil':round(r['soil'],1),'40% less water':round(min(100,reduced_score),1)})
        st.markdown('**Compare the top 3 rotations**')
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
        reason='Different botanical families improve the model diversity score.' if CROPS[best['first']]['family']!=CROPS[best['second']]['family'] else 'Both crops belong to the same botanical family, reducing the diversity score.'
        st.markdown(f'**Why this rotation?** Seasonal temperature, rainfall, estimated irrigation and soil texture are compared for each crop’s planting window. {reason} The previous crop also influences ranking.')
        if best['water']<85:st.warning('Water caution: estimated available water may not meet the assumed crop requirement.')
        st.caption('40% less water is a hypothetical scenario, not measured savings. Scores are illustrative, not validated crop advice or yield predictions.')
        st.link_button('View NASA POWER source data',source_url)
        with st.expander('Data sources & limitations'):
            st.write('NASA POWER monthly T2M and PRECTOTCORR provide historical gridded temperature and precipitation. Monthly precipitation (mm/day) is converted to monthly totals. Crop temperature ranges, irrigation needs, soil texture scores and rotation weights are illustrative assumptions. The model is not validated for actual farm decisions; seek local agronomic guidance.')
    except Exception as exc:st.error(f'Unable to complete analysis: {exc}')
else:
    st.caption('Choose your farm details and press Analyze farm to see a single comparison table.')
