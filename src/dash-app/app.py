import datetime
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import requests
from pymodbus.client.sync import ModbusTcpClient
from dash.dependencies import Input, Output

main_div_style = {
	'backgroundColor': '#111111',
	'color': '#fca503',
	'height': '90vh'
}

divStyle = {
	'backgroundColor': '#111111',
	'color': '#fca503'
}

graphStyle = {
	'plot_bgcolor': '#111111',
	'paper_bgcolor': '#111111',
	'font': {
		'color': '#fca503'
	}
}

app = dash.Dash(__name__)
app.layout = html.Div(
	style = divStyle,
	children = [
	html.Div(
		style = main_div_style,
		children = [
		html.Div(id='live-update-text'),
		dcc.Graph(id='live-update-graph'),
		dcc.Interval(
			id='text-interval-component',
			interval=5000,  # in milliseconds
			n_intervals=0
		),
		dcc.Interval(
			id='graph-interval-component',
			interval=60000,  # in milliseconds
			n_intervals=0
			)
		])]
)


@app.callback(Output('live-update-text', 'children'), [Input('text-interval-component', 'n_intervals')])
def update_text_metrics(n):
	table_elements = []
	header_row = []
	td_style = {'border': '1px solid #fca503', 'text-align' : 'center', 'font-size': '30px', 'font-family': 'cursive'}
	resp = requests.get('http://10.0.10.128/A0')
	current_load = 'N/A'
	if resp.status_code == 200:
		resp_dict = resp.json()
		print('Received: ')
		print(resp_dict)
		current_load = '{0:.2f} A'.format(resp_dict['A0'])
		table_elements.append(html.Td(style=td_style, children=current_load))
		header_row.append(html.Th(style=td_style, children='Battery Load'))
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)

	modbus_client = ModbusTcpClient('10.0.10.10', port=502)
	try:
		modbus_client.connect()
		rr = modbus_client.read_holding_registers(0, 91, unit=1)
		if rr is None:
			modbus_client.close()
			print("Failed to connect and read from tristar modbus")
		else:
			voltage_scaling_factor = (float(rr.registers[0]) + (float(rr.registers[1]) / 100))
			amperage_scaling_factor = (float(rr.registers[2]) + (float(rr.registers[3]) / 100))

			# Voltage Related Statistics
			battery_voltage = float(rr.registers[24]) * voltage_scaling_factor * 2 ** (-15)
			table_elements.append(html.Td(style=td_style, children='{0:.2f} V'.format(battery_voltage)))
			header_row.append(html.Th(style=td_style, children='Battery Voltage'))
			table_elements.append(html.Td(style=td_style, children='{0:0.0f} Watts'.format(battery_voltage * resp_dict['A0'])))
			header_row.append(html.Th(style=td_style, children='Load Watts'))
			battery_sense_voltage = float(rr.registers[26]) * voltage_scaling_factor * 2 ** (-15)
			battery_voltage_slow = float(rr.registers[38]) * voltage_scaling_factor * 2 ** (-15)
			battery_daily_minimum_voltage = float(rr.registers[64]) * voltage_scaling_factor * 2 ** (-15)
			battery_daily_maximum_voltage = float(rr.registers[65]) * voltage_scaling_factor * 2 ** (-15)
			target_regulation_voltage = float(rr.registers[51]) * voltage_scaling_factor * 2 ** (-15)
			array_voltage = float(rr.registers[27]) * voltage_scaling_factor * 2 ** (-15)
			# Current Related Statistics
			array_charge_current = float(rr.registers[29]) * amperage_scaling_factor * 2 ** (-15)
			battery_charge_current = float(rr.registers[28]) * amperage_scaling_factor * 2 ** (-15)
			battery_charge_current_slow = float(rr.registers[39]) * amperage_scaling_factor * 2 ** (-15)
			# Wattage Related Statistics
			input_power = float(rr.registers[59]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
			output_power = float(rr.registers[58]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
			table_elements.append(html.Td(style=td_style, children='{0:0.0f} Watts'.format(output_power)))
			header_row.append(html.Th(style=td_style, children='Solar Array Watts'))
			# Temperature Statistics
			heatsink_temperature = rr.registers[35]
			battery_temperature = rr.registers[36]
			# Misc Statistics
			charge_states = ["START", "NIGHT_CHECK", "DISCONNECT", "NIGHT", "FAULT", "MPPT", "ABSORPTION", "FLOAT",
							 "EQUALIZE",
							 "SLAVE"]
			charge_state = charge_states[rr.registers[50]]
			table_elements.append(html.Td(style=td_style, children=charge_state))
			header_row.append(html.Th(style=td_style, children='Charge State'))
			seconds_in_absorption_daily = rr.registers[77]
			seconds_in_float_daily = rr.registers[79]
			seconds_in_equalization_daily = rr.registers[78]
			modbus_client.close()

	except Exception as e:
		print("Failed to connect to tristar modbus" + e)
		modbus_client.close()

	return html.Table(style={'width': '100vw', 'border': '1px solid #fca503'},
					children=[html.Tr(header_row), html.Tr(table_elements)])

@app.callback(Output('live-update-graph', 'figure'), [Input('graph-interval-component', 'n_intervals')])
def update_graph_live(n):
	fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
	resp = requests.get('http://10.0.10.128/A0')
	current_load = 'N/A'
	if resp.status_code == 200:
		resp_dict = resp.json()
		print('Received: ')
		print(resp_dict)
		graphData['time'].append(datetime.datetime.now())
		graphData['cabinload'].append(resp_dict['A0'])
		if len(graphData) > 1440:
			graphData['time'].pop(0)
			graphData['cabinload'].pop(0)

		fig['layout'] = graphStyle;
		fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
		fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}
		fig.append_trace({'x': graphData['time'], 'y': graphData['cabinload'], 'name': 'Load', 'mode': 'lines+markers',
					  'type': 'scatter'}, 1, 1)
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)
	return fig


def main():
	global graphData
	graphData = {'cabinload': [], 'time': []}
	app.run_server(debug=True, host='0.0.0.0')

if __name__ == '__main__':
	main()
