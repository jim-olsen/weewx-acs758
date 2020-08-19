import datetime
import json
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import requests
from dash.dependencies import Input, Output

app = dash.Dash(__name__)
app.layout = html.Div(
	html.Div([
		html.H4('Cabin Electric Load'),
		html.Div(id='live-update-text'),
		dcc.Graph(id='live-update-graph'),
		dcc.Interval(
			id='interval-component',
			interval=1 * 5000,  # in milliseconds
			n_intervals=0
		)
	])
)


@app.callback(Output('live-update-text', 'children'), [Input('interval-component', 'n_intervals')])
def update_graph_metrics(n):

	resp = requests.get('http://10.0.10.128/A0')
	if resp.status_code == 200:
		json_str = resp.json()
		print('Received: ')
		print(json_str)
		vals = json.loads(json_str)
		graphData['time'].append(datetime.datetime.now())
		graphData['cabinload'].append(vals['A0'])
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)

	[Input('interval-component', 'n_intervals')]


def update_metrics(n):
	resp = requests.get('http://10.0.10.128/A0')
	if resp.status_code == 200:
		json_str = resp.json()
		print('Received: ')
		print(json_str)
		vals = json.loads(json_str)
		graphData['time'].append(datetime.datetime.now())
		graphData['cabinload'].append(vals['A0'])
		style = {'padding': '2px', 'fontSize': '16px'}
		return [
			html.Span('Cabin Load: {}'.format(vals['A0']), style=style)
		]
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)

	return []


@app.callback(Output('live-update-graph', 'figure'), [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
	fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
	fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
	fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}
	fig.append_trace({'x': graphData['time'], 'y': graphData['cabinload'], 'name': 'Load', 'mode': 'lines+markers',
						'type': 'scatter'}, 1, 1)
	return fig


def main():
	global graphData
	graphData = {'cabinload': [], 'time': []}
	app.run_server(debug=True, host='0.0.0.0')


if __name__ == '__main__':
	main()
