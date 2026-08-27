from dash import html
import dash_bootstrap_components as dbc
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os.path
import plotly.express as px
from app import app 
from components.engine import functions
import pandas as pd
from sklearn.preprocessing import StandardScaler


#Importation des données pour le graphique
df_classification=pd.read_csv(functions.FEATURES_CSV,sep=',')
df2 = df_classification[['rms_var','mfcc1_mean']]
df3 = df_classification[['Song','family_genre','Main_Genre']]
scaler = StandardScaler()
scaler.fit(df2)
df_scaled = scaler.transform(df2)
df_scaled = pd.DataFrame(data=df_scaled, columns=['rms_var','mfcc1_mean'])
df_classification = df3.merge(df_scaled,how='left',right_index=True,left_index=True)


fig = px.scatter(data_frame = df_classification, x= "rms_var", y="mfcc1_mean",
                color='Main_Genre',title='Classification of music genre ' )
#######################################

page_title= html.Div([
                    html.H1('Summary',style={'color':'white'}),
                    ], className='page-title-box')


graph_classification=html.Div([
                            dcc.Graph(figure=fig),
                    ],className='graph-classification')

introduction_summary=html.Div([
                    html.P('Music Information Retrieval (MIR) involves searching and organising large collections of music, or music information, according to their relevance to specific queries. This is particularly relevant given the vast quantities of musical information available in digital format, and the popularity of music-related digital services.'
                    ),
                    ],className='introduction-summary')

bloc_summary= html.Div([
                    html.P('Classification, which is one the many possibilities of MIR studies, lets companies either be able to place recommendations to their customers (such as Spotify, Soundcloud) or simply as a product (for example Shazam). Determining music genres is a first milestone to reach. Machine Learning techniques have proved to be quite successful in extracting trends and patterns from the large pool of data. The same principles are applied in Music Analysis also.'
                    ,style={'textAlign':'justify','color':'white'}),
                    html.P('With this project, we have studied how to analyse an audio/music signal in Python. We then have used the skills learnt to classify music clips into different genres.'
                    ,style={'textAlign':'justify','color':'white'}),
                    html.P('How does Audio Processing work ?'
                    ,style={'textAlign':'justify','color':'white'}),
                    html.P('Sound is represented in the form of an audio signal having parameters such as frequency, bandwidth, decibel etc. A typical audio signal can be expressed as a function of Amplitude and Time. Python has some great libraries for audio processing like Librosa and PyAudio.There are also built-in modules for some basic audio functionalities.'
                    ,style={'textAlign':'justify','color':'white'}),
                ],className='bloc-summary')


layout = html.Div([

        dbc.Row([
            page_title
            ],),
        
        dbc.Row([
            introduction_summary
            ],),

        dbc.Row([
            dbc.Col(
                bloc_summary
                    ),
            dbc.Col(
                graph_classification
                ),
        ],)
                
        ], id="summary-layout")
