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

st.set_page_config(page_title='FarmShift | Crop Rotation Planner', page_icon='🌿', layout='wide', initial_sidebar_state='expanded')
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
.stApp {background:#F8F7F2;color:#21392B} .block-container {max-width:1260px;padding-top:1.5rem;padding-bottom:4rem}
[data-testid="stSidebar"] {background:#173D2E} [data-testid="stSidebar"] * {color:#F8F7F2!important}
h1,h2,h3 {color:#173D2E!important;letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;border:1px solid #E3E9DD;border-radius:17px;padding:17px}
[data-testid="stMetricLabel"] {font-weight:650} [data-testid="stDataFrame"] {border-radius:14px}
.stButton button[kind="primary"],div[data-testid="stFormSubmitButton"] button {background:#245D42!important;color:white!important;border-radius:12px!important;border:0!important;min-height:48px}
.stTabs [data-baseweb="tab-list"] {gap:16px;border-bottom:1px solid #DDE5D9}
.stTabs [data-baseweb="tab"] {font-weight:700;font-size:1rem;color:#45614E}
.stTabs [aria-selected="true"] {color:#194B33!important}
.hero {background:linear-gradient(110deg,#E2EAD9,#F6F4E9);border:1px solid #DAE5D6;border-radius:22px;padding:27px 32px;margin:4px 0 22px}
.hero h1 {font-size:2.3rem;margin:0 0 7px}.hero p{color:#526C58;margin:0}
.section {font-size:1.25rem;font-weight:750;color:#1B4632;margin:14px 0 8px}
.hint {color:#6D7B6F;font-size:.88rem}.eyebrow {font-size:.72rem;letter-spacing:2px;font-weight:750;color:#58745F}
.panel {background:white;border:1px solid #E1E8DE;border-radius:18px;padding:20px 24px;margin:12px 0}
.flowchip {background:#E8EFE4;color:#28513B;border-radius:9px;padding:10px 12px;text-align:center;font-weight:700}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, div[data-testid="stMarkdownContainer"] label {color:#203E2D!important;font-weight:650!important;opacity:1!important}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color:white!important}
[data-testid="stForm"] {background:#FFFFFF;border:1px solid #DEE7DC;border-radius:16px;padding:18px}
[data-testid="stSlider"] p, [data-testid="stCheckbox"] p {color:#203E2D!important}
[data-testid="stTextInput"] input {direction:ltr!important;text-align:left!important;unicode-bidi:plaintext!important;font-family:Arial,sans-serif!important}
[data-testid="stNumberInput"] input {direction:ltr!important;text-align:left!important;font-family:Arial,sans-serif!important}
[data-testid="stAlert"] p {color:inherit!important}
</style>""",unsafe_allow_html=True)

with st.sidebar:
    st.markdown('## 🌿 FarmShift')
    st.caption('CROP ROTATION PLANNER')
    st.markdown('---')
    st.markdown('**NASA Space Apps Challenge**')
    st.caption('Tabuk pilot · adaptable to other locations')
    page=st.radio('Navigation',['1 · Farm Setup','2 · Farm Analysis'],key='navigation',label_visibility='collapsed')
    st.markdown('---')
    st.caption('Historical NASA POWER climate observations. Crop scoring is an illustrative prototype, not validated farming advice.')
st.markdown('''<div class="hero"><div class="eyebrow">NASA SPACE APPS CHALLENGE · TABUK PILOT</div><h1>FarmShift <span style="font-weight:400;color:#68856A">/ Smarter rotations.</span></h1><p>Plan healthier crop rotations with real NASA climate data and your farm information.</p></div>''',unsafe_allow_html=True)
st.caption('01 · Farm Setup     /     02 · Farm Analysis')
if 'coords' not in st.session_state:
    st.session_state.coords=(28.445477,36.649388)
if 'analyzed' not in st.session_state:
    st.session_state.analyzed=False
if page=='1 · Farm Setup':
    st.markdown('<div class="section">📍 Farm location</div>',unsafe_allow_html=True)
    st.caption('Click the map to select a farm location, or enter latitude and longitude manually. The map selection updates the coordinate fields.')
    mc,lc=st.columns([1.35,1],gap='large')
    with mc:
        center=st.session_state.coords
        m=folium.Map(location=list(center),zoom_start=11,tiles='OpenStreetMap')
        folium.Marker(list(center),tooltip='Selected farm location',icon=folium.Icon(color='green')).add_to(m)
        st.caption('Map tiles require an internet connection. You can always enter coordinates manually.')
        clicked=st_folium(m,height=310,width=None,returned_objects=['last_clicked'],key='farm_map')
        if clicked and clicked.get('last_clicked'):
            loc=clicked['last_clicked']; selected=(round(loc['lat'],6),round(loc['lng'],6))
            if selected!=st.session_state.coords:
                st.session_state.coords=selected
                st.rerun()
    with lc:
        st.markdown('**Selected location**')
        # Text fields keep ASCII digits independent of the browser's Arabic numeral locale.
        if st.session_state.get('coord_display') != st.session_state.coords:
            st.session_state.lat_ascii=f'{st.session_state.coords[0]:.6f}'
            st.session_state.lon_ascii=f'{st.session_state.coords[1]:.6f}'
            st.session_state.coord_display=st.session_state.coords
        lat_text=st.text_input('Latitude (°)',key='lat_ascii',help='Use English digits, e.g. 28.445477')
        lon_text=st.text_input('Longitude (°)',key='lon_ascii',help='Use English digits, e.g. 36.649388')
        lat,lon=st.session_state.coords
        if st.button('Update map location',use_container_width=True):
            try:
                if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',lat_text.strip()) or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',lon_text.strip()):
                    raise ValueError('Enter coordinates using English digits (0–9) and a decimal point.')
                lat,lon=float(lat_text),float(lon_text)
                if not (-90<=lat<=90 and -180<=lon<=180):
                    raise ValueError('Latitude must be -90 to 90; longitude -180 to 180.')
                st.session_state.coords=(lat,lon)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.caption('NASA POWER uses gridded climate observations; the selected point is not an on-farm weather station.')
    st.markdown('<div class="section">🌱 Farm and planting details</div>',unsafe_allow_html=True)
    with st.form('farm_inputs'):
        a,b=st.columns(2,gap='large')
        with a:
            previous=st.selectbox('Previous crop',list(CROPS),index=0)
            soil=st.selectbox('Soil texture',['Loamy','Sandy','Clay','Silty'])
            year=st.selectbox('Historical season ending year',list(range(2025,2018,-1)))
            start_name=st.selectbox('First crop planting month',MONTHS,index=10)
            duration=st.slider('First crop growing period (months)',2,8,5)
        with b:
            water=st.slider('Available irrigation water (mm per season)',0,800,275,25)
            priority=st.selectbox('Crop rotation objective',['Balanced','Water conservation','Soil health'])
            has_soil=st.checkbox('I have soil test results (optional)')
            ph=ec=None
            if has_soil:
                ph=st.number_input('Soil pH (laboratory result)',0.0,14.0,7.2,0.1)
                ec=st.number_input('Soil salinity — EC (dS/m)',0.0,40.0,1.0,0.1)
            else:
                st.info('Soil pH and salinity are not assumed. Add laboratory values if available.')
            st.caption('The second crop begins after the first crop finishes. Crop-specific durations are prototype assumptions.')
        submit=st.form_submit_button('🌿 Analyze farm →',use_container_width=True)
        if submit:
            st.session_state.params={'lat':lat,'lon':lon,'year':year,'previous':previous,'soil':soil,'ph':ph,'ec':ec,'water':water,'priority':priority,'first_start':MONTHS.index(start_name)+1,'duration':duration}
            st.session_state.analyzed=True
            st.success('Farm details saved. Select 2 · Farm Analysis in the left navigation to see your results.')
            st.session_state.navigation='2 · Farm Analysis'
            st.rerun()
if page=='2 · Farm Analysis':
    if not st.session_state.analyzed:
        st.info('Start in 1 · Farm Setup, enter your farm details and select Analyze farm. Your NASA-powered results will appear here.')
    else:
        p=st.session_state.params
        lat,lon,year,previous,soil,ph,ec,water,priority,first_start,duration=[p[k] for k in ('lat','lon','year','previous','soil','ph','ec','water','priority','first_start','duration')]
        st.markdown('<div class="section">Farm analysis dashboard</div>',unsafe_allow_html=True)
        st.caption(f'Location: {lat:.5f}°, {lon:.5f}° · Historical season ending {year} · Priority: {priority}')
        try:
            with st.spinner('Fetching historical NASA POWER observations...'):
                df,source_url=nasa_monthly(lat,lon,year-2,year+1)
            first_season=get_season(df,year,first_start,duration)
            if first_season is None:raise ValueError('NASA did not return all months for the selected planting season.')
        except Exception as ex:
            st.error(f'NASA POWER data could not be loaded: {ex}')
            st.stop()
        st.success('Live NASA POWER response loaded')
        st.link_button('View original NASA response ↗',source_url)
        st.caption('NASA POWER gridded historical climate data. Monthly precipitation rates (mm/day) are converted into monthly totals (mm).')
        mean_temp=float((first_season.temperature_c*first_season.days).sum()/first_season.days.sum())
        season_rain=float(first_season.rainfall_mm.sum())
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Season temperature',f'{mean_temp:.1f} °C')
        c2.metric('Season rainfall',f'{season_rain:.1f} mm')
        c3.metric('Growing period',f'{duration} months')
        c4.metric('Irrigation allowance',f'{water} mm')
        st.markdown('<div class="section">☀️ NASA climate insights</div>',unsafe_allow_html=True)
        chart=first_season.copy()
        chart['label']=chart.apply(lambda r:f"{calendar.month_abbr[int(r.month)]} {int(r.year)}",axis=1)
        l,r=st.columns(2)
        with l:
            fig=go.Figure(go.Scatter(x=chart.label,y=chart.temperature_c,mode='lines+markers',line=dict(color='#32694C',width=3),marker=dict(size=8)))
            fig.update_layout(title='Monthly temperature · °C',paper_bgcolor='white',plot_bgcolor='white',font_color='#294534',height=310,margin=dict(l=30,r=15,t=55,b=30),xaxis=dict(showgrid=False),yaxis=dict(gridcolor='#E6ECE4'))
            st.plotly_chart(fig,use_container_width=True)
        with r:
            fig=go.Figure(go.Bar(x=chart.label,y=chart.rainfall_mm,marker_color='#93AE88'))
            fig.update_layout(title='Monthly rainfall · mm',paper_bgcolor='white',plot_bgcolor='white',font_color='#294534',height=310,margin=dict(l=30,r=15,t=55,b=30),xaxis=dict(showgrid=False),yaxis=dict(gridcolor='#E6ECE4'))
            st.plotly_chart(fig,use_container_width=True)
        rows=[]
        for first in CROPS:
            if first==previous:continue
            first_stats=crop_score(first,first_season,water,soil,ph,ec)
            second_start=(first_start-1+duration)%12+1
            for second in CROPS:
                if second==first:continue
                second_duration=CROPS[second]['months']
                second_year=season_years(year,first_start,duration)[0]+(first_start-1+duration)//12
                second_season=get_season(df,year,second_start,second_duration,explicit_start_year=second_year)
                if second_season is None:continue
                second_stats=crop_score(second,second_season,water,soil,ph,ec)
                climate=(first_stats['climate']+second_stats['climate'])/2
                water_score=(first_stats['water']+second_stats['water'])/2
                soil_score=(first_stats['soil']+second_stats['soil'])/2
                diversity=100 if CROPS[first]['family']!=CROPS[second]['family'] else 45
                previous_bonus=10 if CROPS[previous]['family']!=CROPS[first]['family'] else 0
                weights={'Balanced':(.35,.35,.2,.1),'Water conservation':(.25,.55,.1,.1),'Soil health':(.25,.2,.3,.25)}[priority]
                score=sum(x*w for x,w in zip((climate,water_score,soil_score,diversity),weights))+previous_bonus*.5
                rows.append({'Crop sequence':f'{first} → {second}','Suitability score':round(min(100,score),1),'Climate':round(climate,1),'Water':round(water_score,1),'Soil':round(soil_score,1),'Rotation diversity':diversity,'first':first,'second':second,'second_start':second_start,'second_year':second_year,'second_duration':second_duration,'previous_bonus':previous_bonus})
        if not rows:
            st.warning('No complete historical season found for this selection. Try a different historical year or planting duration.')
            st.stop()
        ranked=sorted(rows,key=lambda x:x['Suitability score'],reverse=True)
        best=ranked[0]
        st.markdown('<div class="section">🌾 Recommended crop rotation</div>',unsafe_allow_html=True)
        st.markdown(f'''<div class="panel"><div class="eyebrow">TOP-RANKED ILLUSTRATIVE OPTION</div><h2 style="margin:8px 0;color:#17452F">{best['first']} &nbsp; → &nbsp; {best['second']}</h2><div style="font-size:1.1rem;color:#536B58">Suitability index: <b>{best['Suitability score']}/100</b> · First planting: {calendar.month_name[first_start]} · Next planting: {calendar.month_name[best['second_start']]}</div></div>''',unsafe_allow_html=True)
        a,b,c,d=st.columns(4)
        a.metric('Climate fit',f"{best['Climate']}/100")
        b.metric('Water fit',f"{best['Water']}/100")
        c.metric('Soil fit',f"{best['Soil']}/100")
        d.metric('Rotation diversity',f"{best['Rotation diversity']}/100")
        st.markdown('### Why this rotation?')
        st.write(f"**{best['first']}** is evaluated from **{calendar.month_name[first_start]}** for **{duration} months**; **{best['second']}** follows in **{calendar.month_name[best['second_start']]}** for **{best['second_duration']} months**. Each crop is scored against historical climate for its own growing window.")
        if CROPS[best['first']]['family']!=CROPS[best['second']]['family']:
            st.write('**Potential benefit:** switching botanical families can diversify crop management. This does not demonstrate a measured increase in soil nutrients or yield.')
        else:
            st.write('**Trade-off:** both crops share a botanical family, so the model assigns a lower diversity score.')
        if best['Water']<85:st.warning('Water risk: modeled irrigation and rainfall may be below the assumed crop requirements.')
        if best['Climate']<85:st.warning('Climate risk: seasonal mean temperature may fall outside an assumed crop range.')
        st.markdown('### Compare rotation options')
        st.dataframe(pd.DataFrame([{k:r[k] for k in ['Crop sequence','Suitability score','Climate','Water','Soil','Rotation diversity']} for r in ranked[:6]]),hide_index=True,use_container_width=True)
        st.markdown('### 💧 Water stress scenario')
        reduced=water*.6
        st.caption(f'Compare current irrigation allowance ({water} mm/season) against a 40% reduction ({reduced:.0f} mm/season). These are model scores, not measured water savings.')
        scenario=[]
        for row in ranked[:6]:
            a=crop_score(row['first'],first_season,reduced,soil,ph,ec)
            second_season=get_season(df,year,row['second_start'],row['second_duration'],explicit_start_year=row['second_year'])
            b=crop_score(row['second'],second_season,reduced,soil,ph,ec)
            w=(a['water']+b['water'])/2
            weights={'Balanced':(.35,.35,.2,.1),'Water conservation':(.25,.55,.1,.1),'Soil health':(.25,.2,.3,.25)}[priority]
            stressed=sum(x*z for x,z in zip((row['Climate'],w,row['Soil'],row['Rotation diversity']),weights))+row['previous_bonus']*.5
            scenario.append({'Rotation':row['Crop sequence'],'Current score':row['Suitability score'],'40% less irrigation':round(min(100,stressed),1)})
        st.dataframe(pd.DataFrame(scenario),hide_index=True,use_container_width=True)
        with st.expander('Data sources and scientific limitations'):
            st.markdown('''**NASA source:** NASA POWER monthly T2M and PRECTOTCORR for the chosen coordinates. Monthly precipitation rates are converted from mm/day to estimated monthly totals.

**Farmer inputs:** coordinates, previous crop, soil texture, optional pH and EC, irrigation allowance, planting month and duration.

**Prototype assumptions:** crop temperature ranges, water needs, soil response and scoring weights are illustrative. Historical climate is reused for comparison; this is not a future climate forecast.

**Not validated:** crop yields, real irrigation savings, soil nutrient changes, agronomic suitability and local planting recommendations. Confirm any farm decision with local agricultural expertise.''')
