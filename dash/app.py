import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.graph_objs as go
from sqlalchemy import create_engine

def dfcol_to_datetime(df_col):
    formatting = "%Y-%m-%d %H:%M:%S"
    pd.to_datetime(df_col, format=formatting)

def character_skill_filter(df, name, skill, _filter):
    return df[(df.character_name == name) & (df.skill_name == skill)][_filter]

def serve_layout():
    conn = engine.connect()
    exp_df = pd.read_sql("select * from mindstate_r", conn)
    arcana_df = pd.read_sql("select * from mindstate_r where character_name = 'Crannach' and skill_name = 'Arcana'", conn)

    astro_df = pd.read_sql("select * from mindstate_r where character_name = 'Crannach' and skill_name = 'Astrology'", conn)
    conn.close()
    return html.Div(style={'backgroundColor': colors['background']}, children=[
        html.H3(
            children='Revenant: MUD Navelgazing',
            style={
                'textAlign': 'center',
            }
        ),


        html.H4(children='Mindstate vs Time for Crannach', style={'textAlign': 'center'}),
        html.Label('Dropdown'),
        dcc.Dropdown(
            options=[{'label': 'NYC', 'value': 'NYC'}],
            value='NYC'
            ),
        dcc.Graph(
            id='crannach-mindstate',
            figure={
                'data': [
                    #go.Scatter(x=pd.to_datetime(character_skill_filter(exp_df, 'Crannach', 'Targeted Magic', 'timestamp'), format="%Y-%m-%d %H:%M:%S"),
                    #           y=character_skill_filter(exp_df, 'Crannach', 'Targeted Magic', 'mindstate_num'), name='TM'),
                    #go.Scatter(x=pd.to_datetime(character_skill_filter(exp_df, 'Crannach', 'Mechanical Lore', 'timestamp'), format="%Y-%m-%d %H:%M:%S"),
                    #           y=character_skill_filter(exp_df, 'Crannach', 'Mechanical Lore', 'mindstate_num'), name='Mech Lore'),
                    #go.Scatter(x=pd.to_datetime(arcana_df['timestamp'], format="%Y-%m-%d %H:%M:%S"), y=arcana_df['mindstate_num'], name='Arcana'),
                    #go.Scatter(x=pd.to_datetime(astro_df['timestamp'], format="%Y-%m-%d %H:%M:%S"), y=astro_df['mindstate_num'], name='Astrology'),
                    go.Scatter(x=pd.to_datetime(exp_df[(exp_df.character_name == 'Crannach') & (exp_df.skill_name == 'Debilitation')]['timestamp'], format="%Y-%m-%d %H:%M:%S"),
                               y=exp_df[(exp_df.character_name == 'Crannach') & (exp_df.skill_name == 'Debilitation')]['mindstate_num'], name='Debilitation'),
                ],
                'layout': go.Layout(
                            xaxis={
                                'title': 'Time (UTC)',
                                'rangeselector': {
                                    'buttons': [
                                        {'count': 1, 'label':'1d', 'step': 'day', 'stepmode': 'backward'}, 
                                        {'count': 3, 'label': '3d', 'step': 'day', 'stepmode': 'backward'},
                                        {'step': 'all'}]
                                    },
                                'rangeslider': {},
                                'type': 'date',
                                },
                            yaxis={'title': 'Mindstate'},
                        )
            }
            ),
        html.H4('Trading Mindstate vs Time for Dijkstra', style={'textAlign': 'center'}),
        dcc.Graph(
            id='dijkstra-mindstate',
            figure={
                'data': [
                    go.Scatter(x=pd.to_datetime(exp_df[(exp_df.character_name == 'Dijkstra') & (exp_df.skill_name == 'Trading')]['timestamp'], format="%Y-%m-%d %H:%M:%S"),
                               y=exp_df[(exp_df.character_name == 'Dijkstra') & (exp_df.skill_name == 'Trading')]['mindstate_num'], name='Trading'),
                    ],
                'layout': go.Layout(
                            xaxis={
                                'title': 'Time (UTC)',
                                'rangeselector': {
                                    'buttons': [
                                        {'count': 1, 'label':'1d', 'step': 'day', 'stepmode': 'backward'}, 
                                        {'count': 3, 'label': '3d', 'step': 'day', 'stepmode': 'backward'},
                                        {'step': 'all'}]
                                    },
                                'rangeslider': {},
                                'type': 'date',
                                },
                            yaxis={'title': 'Mindstate'},
                        )
            }
     )   
    ])

engine = create_engine('sqlite:////home/jonas/lich/lich/data/exp-track.db3')
app = dash.Dash()
server = app.server
app.css.append_css({"external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"})
colors = {
    'background': '#FFFFFF',
    'text': '#7FDBFF'
}
app.layout = serve_layout
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', debug=True)

