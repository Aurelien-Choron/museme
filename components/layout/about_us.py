from dash import html
import dash_bootstrap_components as dbc
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os.path

from app import app 
from components.engine import functions


# layout = html.Div([
#                 html.H1('About-us',
#                         style={'textAlign':'center','color':'white'}),
    
# ],)

# layout = html.Div([
#                 dbc.Row([
#                         dbc.Col(lg=1, md=1, sm=0),
#                         dbc.Col(html.Iframe(src='https://www.youtube.com/embed/d_owMehNgxY',style={'width':'560px', 'height':'315px'})),
#                         dbc.Col(html.P('Discover our school !', className='disc')),
#                         dbc.Col(lg=1, md=1, sm=0)
#                     ], align ='center', style={'position': 'absolute','top': '0%','left': '60%'}),
#                 html.Br(),
#                 html.Hr(),
#                 dbc.Row([
#                     dbc.Col(lg=1, md=1, sm = 0),
#                     dbc.Col(html.P('Our Wilders Team'), width = 4, className='team'),
#                     dbc.Col(lg=1, md=1, sm = 0)
#                     ],), 
#                 dbc.Row([
#                     dbc.Col(lg=1, md=1, sm = 0),
#                     dbc.Card([
#                         dbc.CardImg(src="https://drive.google.com/file/d/1yIX2JJk3pETNVirQMnUf6Wx0GVR4cZCO/view?usp=sharing",
#                                     top=True,
#                                     style={"width": "13rem",'margin-left': 'auto', 'margin-right':'auto'}),
#                         dbc.CardBody([
#                                 html.H4("Guillaume", className="card-title"),
#                                 html.P('Product Owner & Data Analyst',className="card-text",),
#                                 dbc.Button("Check her Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-951087139/'),
#                                     ]),],style={"width": "14rem"},),
#                     dbc.Card([
#                         dbc.CardImg(src="https://drive.google.com/file/d/1yIX2JJk3pETNVirQMnUf6Wx0GVR4cZCO/view?usp=sharing",
#                                     top=True,
#                                     style={"width": "13rem",'margin-left': 'auto', 'margin-right':'auto'}),
#                         dbc.CardBody([
#                                 html.H4("Guillaume", className="card-title"),
#                                 html.P('Product Owner & Data Analyst',className="card-text",),
#                                 dbc.Button("Check her Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-951087139/'),
#                                     ]),],style={"width": "14rem"},),
#                     dbc.Card([
#                         dbc.CardImg(src="https://drive.google.com/file/d/1yIX2JJk3pETNVirQMnUf6Wx0GVR4cZCO/view?usp=sharing",
#                                     top=True,
#                                     style={"width": "13rem",'margin-left': 'auto', 'margin-right':'auto'}),
#                         dbc.CardBody([
#                                 html.H4("Guillaume", className="card-title"),
#                                 html.P('Product Owner & Data Analyst',className="card-text",),
#                                 dbc.Button("Check her Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-951087139/'),
#                                     ]),],style={"width": "14rem"},),
#                     dbc.Card([
#                         dbc.CardImg(src="https://drive.google.com/file/d/1yIX2JJk3pETNVirQMnUf6Wx0GVR4cZCO/view?usp=sharing",
#                                     top=True,
#                                     style={"width": "13rem",'margin-left': 'auto', 'margin-right':'auto'}),
#                         dbc.CardBody([
#                                 html.H4("Guillaume", className="card-title"),
#                                 html.P('Product Owner & Data Analyst',className="card-text",),
#                                 dbc.Button("Check her Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-951087139/'),
#                                     ]),],style={"width": "14rem"},),
#                     dbc.Col(lg=1, md=1, sm=0)
#                     ])
#                 ])


page_title= html.Div([
                    html.H1('About us',style={'textAlign':'center','color':'white'}),
                    ], className='page-title-box')

wcs_video_presentation= html.Div([
                                html.P('Discover our school !', className='legend_video_wcs'),
                                html.Iframe(src='https://www.youtube.com/embed/d_owMehNgxY', className="video_wcs"),
                                ], className='box-presentation-wcs')
                                

team_presentation= html.Div([
                            dbc.Row([
                                   html.P('Our Wilders Team', className='team'),]),
                            dbc.Row([
                                   dbc.Card([
                                        dbc.CardImg(src="https://media-exp1.licdn.com/dms/image/C5603AQGrr8_BsfrDjg/profile-displayphoto-shrink_200_200/0/1517551069182?e=1618444800&v=beta&t=UHNH3RBnoujz8-PAdSmh-lCGsXe70yd_Z9waWHoCbZE",className="photo-teamate"),
                                        dbc.CardBody([
                                                html.H4("Guillaume", className="card-title"),
                                                html.P('Data Scientist',className="card-text"),
                                                dbc.Button("Check his Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-76724ab1/', className="button-card-team"),
                                                dbc.Button("His favorite album  ", color="danger", href='https://www.youtube.com/watch?v=7_SzbEO0qvk&ab_channel=KyowMusic', className="button-card-team"),
                                                    ]),
                                            ],className='card-teamate'),
                                    dbc.Card([
                                        dbc.CardImg(src="https://media-exp1.licdn.com/dms/image/C4D03AQHYfr3wlUOMYA/profile-displayphoto-shrink_200_200/0/1612951448462?e=1618444800&v=beta&t=Mo-GPLdZnYvRlNOfu8yGPUXZiP1i5sBzuFtBvOfQHcU",className="photo-teamate"),
                                        dbc.CardBody([
                                                html.H4("Joséphine", className="card-title"),
                                                html.P('Data Analyst',className="card-text"),
                                                dbc.Button("Check her Linkedin", color="primary", href='https://www.linkedin.com/in/jos%C3%A9phine-foy-39aa0b182/', className="button-card-team"),
                                                dbc.Button("Her favorite album ", color="danger", href='https://www.youtube.com/watch?v=h_HYQZq9ZEY&list=PLrc3roRiRWpl0ghQOpsSKE65ZDkHtUfpz', className="button-card-team"),
                                                    ]),
                                            ],className='card-teamate'),
                                    dbc.Card([
                                        dbc.CardImg(src="https://media-exp1.licdn.com/dms/image/C5603AQGAzCdLFlfeeg/profile-displayphoto-shrink_200_200/0/1517552950496?e=1618444800&v=beta&t=P71aOwgChJwEJcGrvw6xD-IzCW0iY68lIGO9FxUGpH4",className="photo-teamate"),
                                        dbc.CardBody([
                                                html.H4("Victor", className="card-title"),
                                                html.P('Data Engineer',className="card-text"),
                                                dbc.Button("Check his Linkedin", color="primary", href='https://www.linkedin.com/in/victorandouard/', className="button-card-team"),
                                                dbc.Button("His favorite album ", color="danger", href='https://www.youtube.com/watch?v=iKbeRqqivdw', className="button-card-team"),
                                                    ]),
                                            ],className='card-teamate'),
                                    dbc.Card([
                                        dbc.CardImg(src="https://media-exp1.licdn.com/dms/image/C4E03AQHHMY05ZB24DA/profile-displayphoto-shrink_800_800/0/1608308410232?e=1618444800&v=beta&t=art52Pt9sNtGHqXk3Fg6asx8rc5z5BoePK2EaLqUvSI",className="photo-teamate"),
                                        dbc.CardBody([
                                                html.H4("Aurélien", className="card-title"),
                                                html.P('Music & Data Scientist',className="card-text"),
                                                dbc.Button("Check his Linkedin", color="primary", href='https://www.linkedin.com/in/aur%C3%A9lien-choron-390503201/', className="button-card-team"),
                                                dbc.Button("His favorite album ", color="danger", href='https://www.youtube.com/watch?v=ff7XiWrvkoc', className="button-card-team"),
                                                    ]),
                                            ],className='card-teamate'),
                                    dbc.Card([
                                        dbc.CardImg(src="https://media-exp1.licdn.com/dms/image/C5603AQHQa_WqzUGElg/profile-displayphoto-shrink_200_200/0/1516287937258?e=1618444800&v=beta&t=4O2juJPicq8w-Rf-IL6zy4RxAfCo7v_w-0-HUX38g7s",className="photo-teamate"),
                                        dbc.CardBody([
                                                html.H4("Karim", className="card-title"),
                                                html.P('Financial Analyst',className="card-text"),
                                                dbc.Button("Check his Linkedin", color="primary", href='https://www.linkedin.com/in/guillaume-decroix-951087139/', className="button-card-team"),
                                                dbc.Button("His favorite album ", color="danger", href='https://www.youtube.com/watch?v=T_IW1wLZhzE&ab_channel=TomaszTrzcinski', className="button-card-team"),
                                                    ]),
                                            ],className='card-teamate'),
                                ],className='all-cards-team'),
                        ], className='box-presentation-team')
                            
layout = html.Div([

        page_title,
        
        team_presentation,

        #wcs_video_presentation

        ], id="about-us-layout")


