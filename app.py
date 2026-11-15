import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

st.set_page_config(page_title='FarmShift | Rotation Planner',page_icon='🌱',layout='wide')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif!important}
.stApp{background:#F7F8F4;color:#263C30}.block-container{max-width:1180px;padding-top:2rem}
[data-testid="stSidebar"]{background:#EEF2EA;border-right:1px solid #DEE5DB}
h1,h2,h3{color:#263C30!important;letter-spacing:-.03em}
[data-testid="stMetric"]{background:#FFFFFF;border:1px solid #E0E8DD;border-radius:12px;padding:16px}
[data-testid="stMetricValue"]{color:#284A35}
.stButton button[kind="primary"]{background:#315D43;color:white;border-radius:8px;border:0}
.stButton button[kind="primary"]:hover{background:#244934;color:white}
.hero{padding:28px 32px;background:#E7EEE3;border-radius:16px;border:1px solid #D9E4D5;margin-bottom:20px}
.eyebrow{font-size:11px;letter-spacing:.14em;color:#5C7965;font-weight:700;text-transform:uppercase}
.hero h1{font-size:36px!important;margin:8px 0!important}.hero p{color:#5D7264;margin:0}
.note{font-size:13px;color:#65776B}
.top-ranked{padding:22px 26px;background:#E7EEE3;border-radius:16px;border:1px solid #D9E4D5;margin:18px 0 14px;color:#263C30}
.top-ranked .top-label{font-size:12px;font-weight:700;letter-spacing:.10em;color:#315D43;text-transform:uppercase}
.top-ranked .top-name{font-size:24px;font-weight:700;color:#263C30;margin:7px 0}
.top-ranked .top-score{font-size:16px;color:#315D43;font-weight:600}
[data-testid="stSidebar"] input{color:#182D20!important}
[data-testid="stSidebar"] label{color:#263C30!important}.stDataFrame{background:white}
</style>''',unsafe_allow_html=True)

# Demonstration assumptions: crop ranges MUST be locally validated before field use.
CROPS={
 'Wheat':dict(family='Cereal',temp=(10,24),water=420,ph=(6.0,7.8),ec=6.0,soils=['Loamy','Clay'],start=11,end=4),
 'Barley':dict(family='Cereal',temp=(9,24),water=310,ph=(6.0,8.0),ec=8.0,soils=['Loamy','Clay','Sandy'],start=11,end=4),
 'Lentil':dict(family='Legume',temp=(11,24),water=280,ph=(6.0,7.7),ec=3.0,soils=['Loamy','Sandy'],start=11,end=4),
 'Chickpea':dict(family='Legume',temp=(13,27),water=350,ph=(6.0,8.0),ec=4.0,soils=['Loamy','Sandy'],start=11,end=4),
}
ROTATIONS=[('Wheat','Lentil'),('Barley','Chickpea'),('Wheat','Barley'),('Lentil','Barley')]
WEIGHTS={'Balanced':(.30,.30,.20,.20),'Save water':(.20,.50,.15,.15),'Soil health':(.20,.20,.20,.40),'Climate suitability':(.50,.20,.15,.15)}

@st.cache_data(ttl=86400,show_spinner=False)
def nasa_data(lat,lon,year):
    # Winter season Nov (year-1) to Apr (year): retrieve BOTH calendar years.
    url='https://power.larc.nasa.gov/api/temporal/daily/point'
    params={'parameters':'T2M,T2M_MAX,PRECTOTCORR','community':'AG','latitude':lat,'longitude':lon,
            'start':f'{year-1}0101','end':f'{year}1231','format':'JSON'}
    r=requests.get(url,params=params,timeout=80);r.raise_for_status()
    payload=r.json(); values=payload['properties']['parameter']
    df=pd.DataFrame(values);df.index=pd.to_datetime(df.index,format='%Y%m%d')
    df=df.apply(pd.to_numeric,errors='coerce').replace([-999,-999.0],float('nan')).sort_index()
    if df['T2M'].count()<450 or df['PRECTOTCORR'].count()<450:
        raise ValueError('Incomplete NASA POWER observations for the selected period.')
    return df,r.url

def season_frame(df,harvest_year,crop):
    p=CROPS[crop]
    start=pd.Timestamp(harvest_year-1,p['start'],1)
    end=pd.Timestamp(harvest_year,p['end'],1)+pd.offsets.MonthEnd(0)
    return df.loc[start:end]

def proximity(value,lo,hi,falloff):
    if pd.isna(value):return 0.0
    return max(0.,100.-falloff*max(lo-value,0,value-hi))

def evaluate(sequence,previous,soil,ph,ec,irrigation,df,year,weights):
    parts=[]; explanations=[]; prev_family=CROPS[previous]['family']
    for name in sequence:
        crop=CROPS[name];frame=season_frame(df,year,name)
        if len(frame)<150 or frame.T2M.isna().mean()>.2:raise ValueError('Missing winter-season observations.')
        temp=frame.T2M.mean();rain=frame.PRECTOTCORR.sum(min_count=1)
        climate=proximity(temp,*crop['temp'],12)
        # Illustrative effective rainfall factor, NOT an irrigation prescription.
        effective_rain=max(0,float(rain))*.65
        water=min(100.,100.*(irrigation+effective_rain)/crop['water'])
        texture=100. if soil in crop['soils'] else (70. if soil=='Unknown' else 55.)
        ph_score=100. if ph is None else proximity(ph,*crop['ph'],30)
        salinity=100. if ec is None else max(0.,100.-25.*max(0.,ec-crop['ec']))
        soil_score=.35*texture+.35*ph_score+.30*salinity
        rotation=95. if crop['family']!=prev_family else 35.
        parts.append(dict(climate=climate,water=water,soil=soil_score,rotation=rotation))
        explanations.append(f'{name}: winter mean {temp:.1f}°C; seasonal rainfall {rain:.1f} mm; indicative crop water target {crop["water"]} mm; previous family {prev_family.lower()}.')
        prev_family=crop['family']
    avg={k:sum(p[k] for p in parts)/len(parts) for k in parts[0]}
    total=sum(avg[k]*w for k,w in zip(('climate','water','soil','rotation'),weights))
    return total,avg,explanations

st.markdown('''<div class="hero"><div class="eyebrow">NASA Space Apps Challenge · Tabuk pilot</div><h1>Smarter rotations. Stronger farms.</h1><p>Explore crop sequences using NASA climate observations and your farm's soil and water conditions.</p></div>''',unsafe_allow_html=True)
with st.sidebar:
    st.title('FarmShift')
    st.caption('Farm settings · English prototype')
    st.subheader('Farm location')
    st.caption('Click a point on the map or edit coordinates.')
    if 'pending_location' in st.session_state:
        st.session_state.lat,st.session_state.lon=st.session_state.pop('pending_location')
    if 'lat' not in st.session_state:st.session_state.lat=28.445477
    if 'lon' not in st.session_state:st.session_state.lon=36.649388
    lat=st.number_input('Latitude',min_value=-90.,max_value=90.,format='%.6f',key='lat')
    lon=st.number_input('Longitude',min_value=-180.,max_value=180.,format='%.6f',key='lon')
    year=st.selectbox('Winter harvest year',[2025,2024,2023,2022,2021])
    previous=st.selectbox('Previous crop',list(CROPS))
    soil=st.selectbox('Soil texture',['Loamy','Sandy','Clay','Unknown'])
    known=st.checkbox('I have a soil laboratory test',value=False)
    ph=st.number_input('Soil pH',min_value=3.,max_value=10.,value=7.2,step=.1) if known else None
    ec=st.number_input('Soil salinity (EC, dS/m)',min_value=0.,max_value=30.,value=2.,step=.1) if known else None
    irrigation=st.slider('Available irrigation per crop season (mm)',0,700,300,10)
    priority=st.selectbox('Main priority',list(WEIGHTS))
    analyze=st.button('Analyze farm',type='primary',use_container_width=True)
    st.caption('Soil values are user-provided; NASA does not measure them here.')

st.subheader('Choose your farm location')
st.caption('Click on the map to set coordinates. The marker shows the selected location. Click Analyze farm after changing the location.')
m=folium.Map(location=[lat,lon],zoom_start=10,tiles='CartoDB positron')
folium.Marker([lat,lon],tooltip='Selected farm location',icon=folium.Icon(color='green',icon='leaf')).add_to(m)
map_result=st_folium(m,height=290,use_container_width=True,key='farm_map',returned_objects=['last_clicked'])
if map_result and map_result.get('last_clicked'):
    selected=map_result['last_clicked'];new_lat=round(selected['lat'],6);new_lon=round(selected['lng'],6)
    if (new_lat,new_lon)!=(lat,lon):
        st.session_state.pending_location=(new_lat,new_lon)
        st.session_state.pop('result',None)
        st.rerun()

if analyze:
    try:
        with st.spinner('Retrieving historical climate data from NASA POWER...'):
            df,source=nasa_data(round(lat,6),round(lon,6),year)
        st.session_state.result=(df,source,lat,lon,year)
    except Exception as exc:
        st.session_state.pop('result',None)
        st.error(f'NASA data could not be retrieved: {exc}')
        st.info('No simulated NASA data are substituted.')

if 'result' not in st.session_state:
    st.info('Set your location and farm details, then click **Analyze farm** to load real NASA climate observations.')
    st.stop()

df,source,used_lat,used_lon,used_year=st.session_state.result
if (lat,lon,year)!=(used_lat,used_lon,used_year):
    st.warning('Location or year changed. Click Analyze farm to refresh NASA observations.');st.stop()

st.success(f'NASA POWER observations loaded · {lat:.6f}, {lon:.6f} · historical winter season ending {year}')
st.markdown(f'[Open original NASA POWER response]({source})')
st.subheader('Climate overview')
season=season_frame(df,year,'Wheat')
a,b,c=st.columns(3)
a.metric('Winter mean temperature',f'{season.T2M.mean():.1f} °C')
b.metric('Winter rainfall',f'{season.PRECTOTCORR.sum():.1f} mm')
c.metric('Winter mean daily maximum',f'{season.T2M_MAX.mean():.1f} °C')
st.caption(f'Winter season: November {year-1}–April {year}. Historical data, not a future forecast.')
monthly=season.resample('MS').agg({'T2M':'mean','PRECTOTCORR':'sum'})
fig=go.Figure()
fig.add_trace(go.Scatter(x=monthly.index,y=monthly.T2M,name='Temperature (°C)',line=dict(color='#416C51',width=3)))
fig.update_layout(title='Monthly winter temperature',paper_bgcolor='white',plot_bgcolor='white',font=dict(color='#304A39'),margin=dict(l=20,r=20,t=45,b=20),height=280)
fig.update_xaxes(showgrid=False);fig.update_yaxes(gridcolor='#E7EDE5')
fig2=go.Figure(go.Bar(x=monthly.index,y=monthly.PRECTOTCORR,marker_color='#8EAA94',name='Rainfall (mm)'))
fig2.update_layout(title='Monthly winter rainfall',paper_bgcolor='white',plot_bgcolor='white',font=dict(color='#304A39'),margin=dict(l=20,r=20,t=45,b=20),height=280)
fig2.update_xaxes(showgrid=False);fig2.update_yaxes(gridcolor='#E7EDE5')
x,y=st.columns(2);x.plotly_chart(fig,use_container_width=True);y.plotly_chart(fig2,use_container_width=True)

st.subheader('Rotation planner')
st.caption('Illustrative two-crop sequences. Both crops use the selected historical winter as a planning proxy, not a future forecast.')
weights=WEIGHTS[priority]
rows=[]
for seq in ROTATIONS:
    label=' → '.join(seq)
    current,parts,notes=evaluate(seq,previous,soil,ph,ec,irrigation,df,year,weights)
    reduced_score,_,_=evaluate(seq,previous,soil,ph,ec,round(irrigation*.6),df,year,weights)
    rows.append({'Crop sequence':label,'Current score':round(current,1),'Reduced-water score':round(reduced_score,1),'notes':notes,'parts':parts})
ranked=sorted(rows,key=lambda r:r['Current score'],reverse=True)[:3]
top=ranked[0]
import html
st.markdown('''<div class="top-ranked"><div class="top-label">🌱 TOP RANKED · Illustrative option</div><div class="top-name">'''+html.escape(top['Crop sequence'])+'''</div><div class="top-score">'''+f"{top['Current score']:.1f}"+''' / 100 · Current irrigation scenario</div></div>''',unsafe_allow_html=True)
st.markdown('#### Compare the top 3 rotations')
water_mode=st.radio('Irrigation scenario',['Current irrigation','40% less irrigation'],horizontal=True,key='water_scenario')
score_key='Current score' if water_mode=='Current irrigation' else 'Reduced-water score'
comparison=pd.DataFrame([{'Crop sequence':r['Crop sequence'],'Suitability score / 100':r[score_key]} for r in ranked])
st.dataframe(comparison,hide_index=True,use_container_width=True)
if water_mode!='Current irrigation':
    st.caption(f'Illustrative scenario: {irrigation} → {round(irrigation*.6)} mm per crop season. This is not a NASA drought forecast or measured water savings.')
else:
    st.caption(f'Current irrigation allowance: {irrigation} mm per crop season.')
st.markdown('#### Why these rotations?')
st.write('Scores compare historical winter temperature, indicative water availability, soil compatibility, and crop-family diversity. Your previous crop and chosen priority also affect ranking.')
st.caption('Scores are preliminary model estimates, not measured yield, field performance, or validated farming advice.')

with st.expander('Data sources, scoring assumptions and limitations'):
    st.write('NASA POWER Daily Point API: T2M, T2M_MAX, PRECTOTCORR; retrieved from the selected coordinates. The raw response link is above.')
    st.write('Winter season is November of the previous calendar year through April of the selected harvest year. Both modeled crop phases reuse this historical winter as a climate proxy, rather than predicting future weather.')
    st.write('Crop temperature ranges, water targets, pH tolerance, EC thresholds, effective rainfall factor (65%), and scoring weights are provisional illustrative assumptions requiring local agronomic validation.')
    st.write('pH and salinity are used only when a soil laboratory test is selected; otherwise these criteria are neutral, not invented measurements. EC must be entered in dS/m, and soil testing methods matter.')
    st.write('NASA POWER climate values have coarse spatial resolution and do not measure field soil conditions. The model does not calculate yield, water savings, nitrogen balance or economic returns.')
    st.write('The reduced-water comparison uses a user-defined 40% irrigation reduction, not a NASA drought prediction. Top three rotations are selected by their current-irrigation score for consistent comparison.')
st.caption('FarmShift · Independent educational prototype for NASA Space Apps Challenge · Not endorsed by NASA.')
