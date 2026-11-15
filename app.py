import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title='FarmShift | Crop Rotation Planner', page_icon='🌿', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.stApp{background:#F7F8F4;color:#24372C}
.block-container{max-width:1180px;padding-top:2.2rem;padding-bottom:3rem}
h1,h2,h3{color:#243D30!important;letter-spacing:-.025em}
h1{font-size:2.8rem!important;font-weight:700!important}
h2{font-size:1.5rem!important}h3{font-size:1.12rem!important}
[data-testid="stSidebar"]{background:#EEF1E9;border-right:1px solid #DEE4D8}
[data-testid="stSidebar"] .block-container{padding-top:1.5rem}
[data-testid="stMetric"]{background:white;border:1px solid #E4E9DF;border-radius:13px;padding:18px 20px;box-shadow:0 2px 9px #25382B08}
[data-testid="stMetricLabel"]{color:#657469}
[data-testid="stMetricValue"]{color:#253F31}
.stButton>button[kind="primary"]{background:#315C43;border:1px solid #315C43;color:white;border-radius:9px;font-weight:600;padding:.65rem 1rem}
.stButton>button[kind="primary"]:hover{background:#254934;border-color:#254934}
[data-testid="stDataFrame"], [data-testid="stExpander"]{border-radius:12px;overflow:hidden}
.hero{background:#E8EFE4;border:1px solid #DBE6D5;border-radius:17px;padding:30px 32px;margin-bottom:24px}
.eyebrow{font-size:11px;letter-spacing:.17em;text-transform:uppercase;color:#64806A;font-weight:700;margin-bottom:12px}
.hero-title{font-size:36px;font-weight:700;letter-spacing:-1.4px;color:#243D30;line-height:1.15}
.hero-sub{color:#66776B;font-size:15px;max-width:640px;line-height:1.65;margin-top:10px}
.section-note{color:#718076;font-size:13px;margin-top:-5px;margin-bottom:15px}
.brand{font-size:23px;font-weight:700;letter-spacing:-1px;color:#2D563D;margin-bottom:3px}
.brand-sub{font-size:11px;letter-spacing:.12em;color:#6D8171;text-transform:uppercase;margin-bottom:25px}
.status{background:#EDF5EB;color:#386047;border:1px solid #D5E8D4;border-radius:8px;padding:12px 15px;margin:14px 0;font-size:13px}
.footnote{font-size:12px;color:#78857B;line-height:1.6}

/* Dark green headings and labels; readable pale green inputs */
.stApp p, .stApp label, [data-testid="stWidgetLabel"] p, [data-testid="stMetricLabel"] p {color:#254632!important}
h1,h2,h3,h4,h5,h6 {color:#173E2B!important}
[data-baseweb="input"] input,[data-baseweb="select"]>div,[data-baseweb="base-input"] input {background:#E1EEDB!important;color:#101C15!important;-webkit-text-fill-color:#101C15!important}
[data-baseweb="select"] span {color:#101C15!important}
[data-testid="stMetricValue"] {color:#173E2B!important}
[data-testid="stTextInput"] input {direction:ltr!important;text-align:left!important;font-variant-numeric:tabular-nums!important}

/* FarmShift refreshed theme: calm dashboard, accessible labels and inputs */
[data-testid="stSidebar"] {background:#123D32!important;border-right:1px solid #0C3128!important}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] .brand,[data-testid="stSidebar"] .brand-sub {color:#F2F8F2!important}
[data-testid="stSidebar"] .brand-sub,[data-testid="stSidebar"] .footnote {color:#C6DDCE!important}
[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-testid="stSidebar"] [data-baseweb="select"]>div,
[data-testid="stSidebar"] [data-baseweb="base-input"] input,
[data-testid="stSidebar"] [data-baseweb="select"] span {
 background:#DCEEDB!important;color:#102C20!important;-webkit-text-fill-color:#102C20!important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg {fill:#173E2B!important;color:#173E2B!important}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] li,
[data-baseweb="menu"], [role="option"] {background:#EFF7EC!important;color:#122F22!important;-webkit-text-fill-color:#122F22!important}
[role="option"]:hover,[aria-selected="true"][role="option"] {background:#C6E3C4!important}
[data-testid="stSidebar"] [data-testid="stExpander"] {background:#1C4B3E!important;border:1px solid #46735E!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary * {color:#F1F8F0!important}
[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stThumbValue"] {color:#F3FFF3!important}
[data-testid="stSidebar"] [data-testid="stSlider"] [role="slider"] {background:#D8EAD6!important}
[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stTickBar"] {color:#F3FFF3!important}
[data-testid="stSidebar"] .stButton>button[kind="primary"] {background:#DCEEDB!important;color:#123C2B!important;border-color:#DCEEDB!important}
[data-testid="stSidebar"] .stButton>button[kind="primary"] p {color:#123C2B!important}
[data-testid="stSidebar"] .stButton>button[kind="primary"]:hover {background:#C5E1C5!important}
.stApp {background:#F8F8F3!important}
.hero {background:#E9F1E6!important}
/* Latin digit rendering in input controls and numerical widgets */
input,[data-testid="stMetricValue"],[data-testid="stDataFrame"] {font-variant-numeric:lining-nums tabular-nums}
</style>''',unsafe_allow_html=True)

# Illustrative agronomic parameters, not validated recommendations for Tabuk.
CROPS = {
    'Wheat': {'family':'cereal','temp':(8,26),'water':(350,550),'soil':['Loamy','Clay','Sandy'],'season':[11,12,1,2,3,4]},
    'Barley': {'family':'cereal','temp':(7,25),'water':(250,450),'soil':['Loamy','Clay','Sandy'],'season':[11,12,1,2,3,4]},
    'Lentil': {'family':'legume','temp':(10,25),'water':(250,400),'soil':['Loamy','Sandy'],'season':[11,12,1,2,3,4]},
    'Chickpea': {'family':'legume','temp':(12,28),'water':(300,500),'soil':['Loamy','Sandy'],'season':[11,12,1,2,3,4]},
}

@st.cache_data(ttl=3600,show_spinner=False)
def nasa_data(lat,lon,year):
    url='https://power.larc.nasa.gov/api/temporal/daily/point'
    params={'parameters':'T2M,T2M_MAX,PRECTOTCORR','community':'AG','longitude':lon,'latitude':lat,'start':f'{year}0101','end':f'{year}1231','format':'JSON'}
    response=requests.get(url,params=params,timeout=55)
    response.raise_for_status()
    values=response.json()['properties']['parameter']
    df=pd.DataFrame(values)
    df.index=pd.to_datetime(df.index,format='%Y%m%d')
    df=df.apply(pd.to_numeric,errors='coerce').replace([-999,-999.0],float('nan'))
    if df['T2M'].count()<250 or df['PRECTOTCORR'].count()<250:
        raise ValueError('NASA data are incomplete for this location or year.')
    return df,response.url

def closeness(value,lo,hi):
    if pd.isna(value): return 0.0
    if lo<=value<=hi: return 100.0
    return max(0.0,100.0-12.0*min(abs(value-lo),abs(value-hi)))

def score_rotation(rotation,previous,soil,water_budget,climate,weights):
    scores=[]
    previous_family=CROPS[previous]['family']
    for name in rotation:
        crop=CROPS[name]
        months=climate[climate.index.month.isin(crop['season'])]
        temperature=float(months['T2M'].mean())
        rain=float(months['PRECTOTCORR'].sum())
        climate_score=closeness(temperature,*crop['temp'])
        need=sum(crop['water'])/2
        water_score=max(0.0,min(100.0,100.0*(water_budget+rain)/need))
        soil_score=100.0 if soil in crop['soil'] else 45.0
        rotation_score=90.0 if crop['family']!=previous_family else 35.0
        scores.append({'climate':climate_score,'water':water_score,'soil':soil_score,'rotation':rotation_score})
        previous_family=crop['family']
    means={k:sum(s[k] for s in scores)/len(scores) for k in ['climate','water','soil','rotation']}
    total=sum(means[k]*weights[k] for k in weights)
    return total,means

st.markdown('''<div class="hero"><div class="eyebrow">NASA Space Apps Challenge · FarmShift</div>
<div class="hero-title">Smarter rotations.<br>Stronger farms.</div>
<div class="hero-sub">Explore crop rotation strategies using NASA climate observations, local soil conditions, and your farming priorities.</div></div>''',unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand">◈ FarmShift</div><div class="brand-sub">Crop Rotation Planner</div>',unsafe_allow_html=True)
    st.subheader('Farm details')
    st.caption('Demo farm location · change anytime')
    if 'farm_lat' not in st.session_state: st.session_state.farm_lat='28.445477'
    if 'farm_lon' not in st.session_state: st.session_state.farm_lon='36.649388'
    with st.expander('🗺️ Choose farm location on map (optional)'):
        st.caption('Click anywhere on the map to set the farm coordinates. Manual entry works without the map.')
        try:
            map_lat=float(st.session_state.farm_lat)
            map_lon=float(st.session_state.farm_lon)
        except ValueError:
            map_lat,map_lon=28.445477,36.649388
        fmap=folium.Map(location=[map_lat,map_lon],zoom_start=9,tiles='OpenStreetMap')
        folium.Marker([map_lat,map_lon],tooltip='Selected farm').add_to(fmap)
        map_result=st_folium(fmap,height=255,use_container_width=True,key='farm_map',returned_objects=['last_clicked'])
        clicked=map_result.get('last_clicked') if map_result else None
        if clicked:
            chosen_lat=f"{clicked['lat']:.4f}"
            chosen_lon=f"{clicked['lng']:.4f}"
            if (chosen_lat,chosen_lon)!=(st.session_state.farm_lat,st.session_state.farm_lon):
                st.session_state.farm_lat=chosen_lat
                st.session_state.farm_lon=chosen_lon
                st.rerun()
    st.text_input('Latitude (English digits)',key='farm_lat',help='Example: 28.445477')
    st.text_input('Longitude (English digits)',key='farm_lon',help='Example: 36.649388')
    try:
        lat=float(st.session_state.farm_lat.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')))
        lon=float(st.session_state.farm_lon.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')))
        valid_coordinates=(-90<=lat<=90 and -180<=lon<=180)
    except ValueError:
        lat,lon,valid_coordinates=28.445477,36.649388,False
    if not valid_coordinates: st.error('Enter valid latitude (-90 to 90) and longitude (-180 to 180).')
    year=st.select_slider('Historical climate year',options=list(range(2020,2026)),value=2025,help='Slide to choose a historical year (2020–2025).')
    previous=st.selectbox('Previous crop',list(CROPS))
    soil=st.selectbox('Soil type',['Loamy','Sandy','Clay','Unknown'])
    water_budget=st.slider('Available irrigation per season (mm)',0,700,300,25)
    priority=st.selectbox('Main priority',['Balanced','Save water','Soil health','Climate suitability'])
    analyze=st.button('Analyze farm',type='primary',use_container_width=True,disabled=not valid_coordinates)
    st.markdown('<div class="footnote">NASA POWER supplies climate observations. Crop requirements and scoring rules are illustrative.</div>',unsafe_allow_html=True)

weights_by_priority={
    'Balanced':{'climate':.30,'water':.30,'soil':.15,'rotation':.25},
    'Save water':{'climate':.20,'water':.50,'soil':.10,'rotation':.20},
    'Soil health':{'climate':.20,'water':.20,'soil':.20,'rotation':.40},
    'Climate suitability':{'climate':.50,'water':.20,'soil':.10,'rotation':.20},
}

if analyze:
    try:
        with st.spinner('Connecting to NASA POWER...'):
            df,source=nasa_data(round(lat,4),round(lon,4),year)
        st.session_state['nasa_result']=(df,source,lat,lon,year)
    except Exception as exc:
        st.session_state.pop('nasa_result',None)
        st.error(f'Unable to retrieve NASA data: {exc}')
        st.info('No simulated climate data were substituted. Check the connection or select another year.')

if 'nasa_result' not in st.session_state:
    st.subheader('Your farm, a clearer next step')
    st.markdown('<div class="section-note">Set your farm details on the left, then select <b>Analyze farm</b> to load real NASA climate observations.</div>',unsafe_allow_html=True)
    x,y,z=st.columns(3)
    x.metric('01 · Location','Demo farm')
    y.metric('02 · Climate','NASA POWER')
    z.metric('03 · Planning','3 rotations')
    st.markdown('---')
    st.subheader('How it works')
    st.write('**Choose a location**  →  **Review climate**  →  **Compare rotations**  →  **Test a water scenario**')
    st.caption('Prototype only. The crop model is not validated for real farming decisions.')
    st.stop()

df,source,used_lat,used_lon,used_year=st.session_state['nasa_result']
if not valid_coordinates or (lat,lon,year)!=(used_lat,used_lon,used_year):
    st.warning('Location or year changed. Select Analyze farm again to refresh NASA data.')
    st.stop()

st.markdown(f'<div class="status">● Live NASA POWER response loaded · {year} · {lat:.4f}° N, {lon:.4f}° E</div>',unsafe_allow_html=True)
st.markdown(f'[View original NASA data response]({source})')
st.subheader('Climate overview')
st.markdown('<div class="section-note">Historical observations for the selected location and year.</div>',unsafe_allow_html=True)
a,b,c=st.columns(3)
a.metric('Mean temperature',f'{df.T2M.mean():.1f} °C')
b.metric('Annual precipitation',f'{df.PRECTOTCORR.sum():.1f} mm')
c.metric('Mean daily maximum',f'{df.T2M_MAX.mean():.1f} °C')
monthly=df.resample('MS').agg({'T2M':'mean','PRECTOTCORR':'sum'})
left,right=st.columns(2,gap='large')
with left:
    st.markdown('**Monthly temperature · °C**')
    st.line_chart(monthly['T2M'],color='#547B60')
with right:
    st.markdown('**Monthly rainfall · mm**')
    st.bar_chart(monthly['PRECTOTCORR'],color='#7199AA')

st.markdown('---')
st.subheader('Rotation planner')
st.markdown('<div class="section-note">Compare two-season crop sequences based on climate, water, soil and crop-family diversity.</div>',unsafe_allow_html=True)
options=[['Wheat','Lentil'],['Barley','Chickpea'],['Wheat','Barley']]
weights=weights_by_priority[priority]
rows=[]
for rotation in options:
    total,parts=score_rotation(rotation,previous,soil,water_budget,df,weights)
    rows.append({'Crop sequence':' → '.join(rotation),'Suitability score':round(total,1),'Climate':round(parts['climate']),'Water':round(parts['water']),'Soil':round(parts['soil']),'Rotation':round(parts['rotation'])})
result=pd.DataFrame(rows).sort_values('Suitability score',ascending=False)
st.dataframe(result,hide_index=True,use_container_width=True)
st.success(f"Top-ranked in this demonstration: {result.iloc[0]['Crop sequence']}")
st.caption('Scores are illustrative suitability indices, not predicted yield gains or water savings. The same historical year is used for both modeled seasons; this is not a forecast.')

st.markdown('---')
st.subheader('What if irrigation water decreases?')
st.markdown('<div class="section-note">Explore a scenario with 40% less available irrigation water. This is a user-defined scenario, not a NASA drought forecast.</div>',unsafe_allow_html=True)
reduced=max(0,int(water_budget*.6))
scenario=[]
for rotation in options:
    base=score_rotation(rotation,previous,soil,water_budget,df,weights)[0]
    drought=score_rotation(rotation,previous,soil,reduced,df,weights)[0]
    scenario.append({'Crop sequence':' → '.join(rotation),'Current score':round(base,1),'Reduced-water score':round(drought,1)})
st.dataframe(pd.DataFrame(scenario).sort_values('Reduced-water score',ascending=False),hide_index=True,use_container_width=True)

with st.expander('Methodology, sources & limitations'):
    st.write('Climate data: NASA POWER Daily Point API. The original response is linked above.')
    st.write('Scoring: weighted mean of illustrative climate fit, water availability, soil compatibility and rotation-family diversity.')
    st.write('Crop thresholds are preliminary demonstration assumptions, not verified Tabuk agronomic guidance. Rainfall is summed over selected months in one calendar year even though winter cropping can span two years.')
    st.write('The model does not measure field soil moisture, salinity, crop yield, evapotranspiration, costs, or future weather. A local agronomist should validate it before any real agricultural use.')

st.markdown('<div class="footnote">FarmShift · Prototype for NASA Space Apps Challenge · NASA data are used independently; this project is not endorsed by NASA.</div>',unsafe_allow_html=True)
