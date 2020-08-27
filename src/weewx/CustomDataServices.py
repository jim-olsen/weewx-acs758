import syslog
import weewx
import requests
import RPi.GPIO as GPIO
import schemas.wview
import weewx.units
import time
import statistics

from pymodbus.client.sync import ModbusTcpClient
from weewx.engine import StdService
from DFRobot_AS3935_Lib import DFRobot_AS3935

amp_data_schema = [{'battery_amp_draw', 'REAL'},
				   {'load', 'REAL'}]

weewx.units.obs_group_dict['battery_amp_draw'] = 'group_amp'
weewx.units.obs_group_dict['load'] = 'group_amp'

# Define our additional supported columns and their types

tristar_schema = [('battery_voltage', 'REAL'),
				  ('battery_sense_voltage', 'REAL'),
				  ('battery_voltage_slow', 'REAL'),
				  ('battery_daily_minimum_voltage', 'REAL'),
				  ('battery_daily_maximum_voltage', 'REAL'),
				  ('target_regulation_voltage', 'REAL'),
				  ('array_voltage', 'REAL'),
				  ('array_charge_current', 'REAL'),
				  ('battery_charge_current', 'REAL'),
				  ('battery_charge_current_slow', 'REAL'),
				  ('input_power', 'REAL'),
				  ('output_power', 'REAL'),
				  ('heatsink_temperature', 'REAL'),
				  ('battery_temperature', 'REAL'),
				  ('charge_state', 'REAL'),
				  ('seconds_in_absorption_daily', 'REAL'),
				  ('seconds_in_float_daily', 'REAL'),
				  ('seconds_in_equalize_daily', 'REAL')]

lightning_schema = [('lightning_total_strikes', 'REAL'),
					('lightning_avg_distance', 'REAL'),
					('lightning_median_distance', 'REAL'),
					('lightning_max_distance', 'REAL'),
					('lightning_avg_intensity', 'REAL'),
					('lightning_median_intensity', 'REAL'),
					('lightning_max_intensity', 'REAL')]

schema_with_custom_data = schemas.wview.schema + tristar_schema + amp_data_schema + lightning_schema

# Define the schema column types for weewx types

weewx.units.obs_group_dict['battery_voltage'] = 'group_volt'
weewx.units.obs_group_dict['battery_sense_voltage'] = 'group_volt'
weewx.units.obs_group_dict['battery_voltage_slow'] = 'group_volt'
weewx.units.obs_group_dict['battery_daily_minimum_voltage'] = 'group_volt'
weewx.units.obs_group_dict['battery_daily_maximum_voltage'] = 'group_volt'
weewx.units.obs_group_dict['target_regulation_voltage'] = 'group_volt'
weewx.units.obs_group_dict['array_voltage'] = 'group_volt'
weewx.units.obs_group_dict['array_charge_current'] = 'group_amp'
weewx.units.obs_group_dict['battery_charge_current'] = 'group_amp'
weewx.units.obs_group_dict['battery_charge_current_slow'] = 'group_amp'
weewx.units.obs_group_dict['input_power'] = 'group_power'
weewx.units.obs_group_dict['output_power'] = 'group_power'
weewx.units.obs_group_dict['heatsink_temperature'] = 'group_temperature'
weewx.units.obs_group_dict['battery_temperature'] = 'group_temperature'
weewx.units.obs_group_dict['charge_state'] = 'group_charge_state'
weewx.units.USUnits['group_charge_state'] = 'cstate'
weewx.units.MetricUnits['group_charge_state'] = 'cstate'
weewx.units.MetricWXUnits['group_charge_state'] = 'cstate'
weewx.units.default_unit_format_dict['cstate'] = '%d'
weewx.units.default_unit_label_dict['cstate'] = ' Charge Mode'
weewx.units.obs_group_dict['seconds_in_absorption_daily'] = 'group_elapsed'
weewx.units.obs_group_dict['seconds_in_float_daily'] = 'group_elapsed'
weewx.units.obs_group_dict['seconds_in_equalize_daily'] = 'group_elapsed'


#
# The data service for gathering information about current draw from the arduino connected to the ACS758 current
# draw detector.  Will add the data records to the archive packet
#
class AddACS758Data(StdService):
	def __init__(self, engine, config_dict):
		super(AddACS758Data, self).__init__(engine, config_dict)

		# Grab the configuration parameters for communication with the charge controller
		try:
			self.arduino_address = config_dict['ACS758']['address']
			self.arduino_port = int(config_dict['ACS758'].get('port', 80))

			# Bind to any new archive record events:
			self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_packet)
			syslog.syslog(syslog.LOG_INFO, "ACS758 configured for address %(address)s port %(port)d" %
						  {"address": self.arduino_address, "port": self.arduino_port})
		except KeyError as e:
			syslog.syslog(syslog.LOG_ERR, "Tristar failed to configure")

	def new_archive_packet(self, event):
		resp = requests.get(self.arduino_address + ':' + str(self.arduino_port) + '/A0')
		if resp.status_code == 200:
			syslog.syslog(syslog.LOG_INFO, "Successfully got battery amps from ACS758")
			dict_result = resp.json()
			event.record['battery_amp_draw'] = dict_result['A0']
		else:
			syslog.syslog(syslog.LOG_ERR, "Failed to retrieve packet from ACS758: " + str(resp.status_code))
		resp = requests.get(self.arduino_address + ':' + str(self.arduino_port) + '/A1')
		if resp.status_code == 200:
			syslog.syslog(syslog.LOG_INFO, "Successfully got battery amps from ACS758")
			dict_result = resp.json()
			event.record['load'] = dict_result['A1']
		else:
			syslog.syslog(syslog.LOG_ERR, "Failed to retrieve packet from ACS758: " + str(resp.status_code))


#
# The data service implementation class itself.  Adds charge controller parameters to the weather record (archive)
# at the time it is received from weewx.  These will be persisted by weewx to the database for later consumption
#
class AddTristarData(StdService):
	def __init__(self, engine, config_dict):
		# Initialize Superclass
		super(AddTristarData, self).__init__(engine, config_dict)

		# Grab the configuration parameters for communication with the charge controller
		try:
			self.tristar_address = config_dict['Tristar']['address']
			self.tristar_port = int(config_dict['Tristar'].get('port', 502))

			# Bind to any new archive record events:
			self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_packet)
			syslog.syslog(syslog.LOG_INFO,
						  "Tristar configured for address %(address)s port %(port)d" % {"address": self.tristar_address,
																						"port": self.tristar_port})
		except KeyError as e:
			syslog.syslog(syslog.LOG_ERR, "Tristar failed to configure")

	#
	# new_archive_packet()
	#   Called by weewx when a new archive packet is received.  Talk to the charge controller and grab the current
	# values from modbus and append to the current archive packet.
	#
	def new_archive_packet(self, event):
		client = ModbusTcpClient(self.tristar_address, port=self.tristar_port)
		try:
			client.connect()
			rr = client.read_holding_registers(0, 92, unit=1)
			if rr is None:
				client.close()
				syslog.syslog(syslog.LOG_ERR, "Failed to connect to tristar")
			else:
				syslog.syslog(syslog.LOG_INFO, "Successfully retrieved packet from Tristar")
				voltage_scaling_factor = (float(rr.registers[0]) + (float(rr.registers[1]) / 100))
				amperage_scaling_factor = (float(rr.registers[2]) + (float(rr.registers[3]) / 100))

				# Voltage Related Statistics
				battery_voltage = float(rr.registers[24]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Voltage: %.2f" % battery_voltage)
				event.record['battery_voltage'] = battery_voltage

				battery_sense_voltage = float(rr.registers[26]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Sense Voltage: %.2f" % battery_sense_voltage)
				event.record['battery_sense_voltage'] = battery_sense_voltage

				battery_voltage_slow = float(rr.registers[38]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Voltage (Slow): %.2f" % battery_voltage_slow)
				event.record['battery_voltage_slow'] = battery_voltage_slow

				battery_daily_minimum_voltage = float(rr.registers[64]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Daily Minimum Voltage: %.2f" % battery_daily_minimum_voltage)
				event.record['battery_daily_minimum_voltage'] = battery_daily_minimum_voltage

				battery_daily_maximum_voltage = float(rr.registers[65]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Daily Maximum Voltage: %.2f" % battery_daily_maximum_voltage)
				event.record['battery_daily_maximum_voltage'] = battery_daily_maximum_voltage

				target_regulation_voltage = float(rr.registers[51]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Target Regulation Voltage: %.2f" % target_regulation_voltage)
				event.record['target_regulation_voltage'] = target_regulation_voltage

				array_voltage = float(rr.registers[27]) * voltage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Array Voltage: %.2f" % array_voltage)
				event.record['array_voltage'] = array_voltage

				# Current Related Statistics
				array_charge_current = float(rr.registers[29]) * amperage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Array Charge Current: %.2f" % array_charge_current)
				event.record['array_charge_current'] = array_charge_current

				battery_charge_current = float(rr.registers[28]) * amperage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Charge Current: %.2f" % battery_charge_current)
				event.record['battery_charge_current'] = battery_charge_current

				battery_charge_current_slow = float(rr.registers[39]) * amperage_scaling_factor * 2 ** (-15)
				syslog.syslog(syslog.LOG_DEBUG, "Battery Charge Current (slow): %.2f" % battery_charge_current_slow)
				event.record['battery_charge_current_slow'] = battery_charge_current_slow

				# Wattage Related Statistics
				input_power = float(rr.registers[59]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
				syslog.syslog(syslog.LOG_DEBUG, "Array Input Power: %.2f" % input_power)
				event.record['input_power'] = input_power

				output_power = float(rr.registers[58]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
				syslog.syslog(syslog.LOG_DEBUG, "Controller Output Power: %.2f" % output_power)
				event.record['output_power'] = output_power

				# Temperature Statistics
				heatsink_temperature = rr.registers[35]
				syslog.syslog(syslog.LOG_DEBUG, "Heatsink Temperature: %(c)d %(f).1f" % {"c": heatsink_temperature,
																						 "f": 9.0 / 5.0 * heatsink_temperature + 32})
				event.record['heatsink_temperature'] = heatsink_temperature

				battery_temperature = rr.registers[36]
				syslog.syslog(syslog.LOG_DEBUG, "Battery Temperature: %(c)d %(f).1f" % {"c": battery_temperature,
																						"f": 9.0 / 5.0 * battery_temperature + 32})
				event.record['battery_temperature'] = battery_temperature

				# Misc Statistics
				charge_states = ["START", "NIGHT_CHECK", "DISCONNECT", "NIGHT", "FAULT", "MPPT", "ABSORPTION", "FLOAT",
								 "EQUALIZE",
								 "SLAVE"]
				charge_state = rr.registers[50]
				syslog.syslog(syslog.LOG_DEBUG,
							  "Charge State %(chargeState)d - %(stateName)s" % {"chargeState": charge_state,
																				"stateName": charge_states[
																					charge_state]})
				event.record['charge_state'] = charge_state

				seconds_in_absorption_daily = rr.registers[77]
				syslog.syslog(syslog.LOG_DEBUG, "Seconds in Absorption: %(seconds)d (%(minutes).1f minutes)" % {
					"seconds": seconds_in_absorption_daily, "minutes": float(seconds_in_absorption_daily) / 60})
				event.record['seconds_in_absorption_daily'] = seconds_in_absorption_daily

				seconds_in_float_daily = rr.registers[79]
				syslog.syslog(syslog.LOG_DEBUG, "Seconds in Float: %d" % seconds_in_float_daily)
				event.record['seconds_in_float_daily'] = seconds_in_float_daily

				seconds_in_equalization_daily = rr.registers[78]
				syslog.syslog(syslog.LOG_DEBUG, "Seconds in Equalization: %d" % seconds_in_equalization_daily)
				event.record['seconds_in_equalization_daily'] = seconds_in_equalization_daily
				client.close()
		except Exception as e:
			syslog.syslog(syslog.LOG_ERR, "Error processing record from tristar: " + str(e))
			client.close()


#
# The data service implementation class itself.  Adds lightning sensor parameters to the weather record (archive)
# at the time it is received from weewx.  These will be persisted by weewx to the database for later consumption
#
class AddLightningData(StdService):
	def __init__(self, engine, config_dict):
		# Initialize Superclass
		super(AddLightningData, self).__init__(engine, config_dict)

		self.lightning_data = []
		# Grab the configuration parameters for communication with the charge controller
		try:
			GPIO.setmode(GPIO.BOARD)
			self.sensor = DFRobot_AS3935(0x03, bus=1)
			if self.sensor.reset():
				syslog.syslog(syslog.LOG_INFO, "init lightning sensor success.")
				# Configure sensor
				self.sensor.powerUp()
				# set indoors or outdoors models
				self.sensor.setIndoors()
				# sensor.setOutdoors()
				# disturber detection
				self.sensor.disturberEn()
				# sensor.disturberDis()
				self.sensor.setIrqOutputSource(0)
				time.sleep(0.5)
				# set capacitance
				self.sensor.setTuningCaps(96)
				# Set the noise level,use a default value greater than 7
				self.sensor.setNoiseFloorLv1(2)
				# used to modify WDTH,values should only be between 0x00 and 0x0F (0 and 7)
				self.sensor.setWatchdogThreshold(2)
				# used to modify SREJ (spike rejection),values should only be between 0x00 and 0x0F (0 and 7)
				self.sensor.setSpikeRejection(2)

				GPIO.setup(7, GPIO.IN)
				GPIO.add_event_detect(7, GPIO.RISING, callback=self.gpio_callback)
			else:
				syslog.syslog(syslog.LOG_ERR, "init lightning sensor fail")
		except KeyError as e:
			syslog.syslog(syslog.LOG_ERR, "Lightning detector failed to configure")

	def gpio_callback(self, channel):
		syslog.syslog(syslog.LOG_INFO, "Received Lightning Interrupt")
		time.sleep(0.005)
		intSrc = self.sensor.getInterruptSrc()
		if intSrc == 1:
			syslog.syslog(syslog.LOG_INFO, "Lightning Detected")
			# Add in the new record to the list of records
			self.lightning_data.append({
				'strike_distance': self.sensor.getLightningDistKm(),
				'strike_intensity': self.sensor.getStrikeEnergyRaw()
			})
		elif intSrc == 3:
			syslog.syslog(syslog.LOG_ERR, "Lightning Detector Noise Level Too High")
		else:
			pass

	#
	# new_archive_packet()
	#   Called by weewx when a new archive packet is received.  Talk to the charge controller and grab the current
	# values from modbus and append to the current archive packet.
	#
	def new_archive_packet(self, event):
		if len(self.lightning_data) > 0:
			syslog(syslog.LOG_INFO, "Lightning strikes detected, processing info")
			event.record['lightning_total_strikes'] = len(self.lightning_data)
			distances = []
			intensities = []
			for rec in self.lightning_data:
				distances.append(rec['strike_distance'])
				intensities.append(rec['strike_intensity'])
			event.record['lightning_avg_distance'] = statistics.mean(distances)
			event.record['lightning_median_distance'] = statistics.median(distances)
			event.record['lightning_max_distance'] = max(distances)
			event.record['lightning_min_distance'] = min(distances)
			event.record['lightning_avg_intensity'] = statistics.mean(intensities)
			event.record['lightning_median_intensity'] = statistics.median(intensities)
			event.record['lightning_max_intensity'] = max(intensities)
		else:
			event.record['lightning_total_strikes'] = 0
			event.record['lightning_avg_distance'] = 0
			event.record['lightning_median_distance'] = 0
			event.record['lightning_max_distance'] = 0
			event.record['lightning_avg_intensity'] = 0
			event.record['lightning_median_intensity'] = 0
			event.record['lightning_max_intensity'] = 0

