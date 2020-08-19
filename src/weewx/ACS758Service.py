import syslog
import weewx
import requests
from weewx.engine import StdService
import schemas schemas.wview
import weewx.units

schema_with_amp_data = schemas.wview.schema + [{'battery_amp_draw', 'REAL'}]

weewx.units.obs_group_dict['battery_amp_draw'] = 'group_amp'

class AddACS758Data(StdService):
	def __init__(self, engine, config_dict):
		super(AddACS758Data, self).__init__(engine, config_dict)

		# Grab the configuration parameters for communication with the charge controller
		try:
			self.arduino_address = config_dict['ACS758']['address']
			self.arduino_port = int(config_dict['ACS758'].get('port', 80))

			# Bind to any new archive record events:
			self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_packet)
			syslog.syslog(syslog.LOG_INFO,
						  "ACS758 configured for address %(address)s port %(port)d" % {"address": self.arduino_address,
																						"port": self.arduino_port})
		except KeyError as e:
			syslog.syslog(syslog.LOG_ERR, "Tristar failed to configure")

	def new_archive_packet(self, event):
		resp = requests.get(self.arduino_address + ':' + self.arduino_port + '/A0')
		if (resp.status_code == 200):
			syslog.syslog(syslog.LOG_INFO, "Successfully got amps from ACS758")
			dict_result = resp.json();
			event.record['battery_amp_draw'] = dict_result['A0']
		else:
			syslog.syslog(syslog.LOG_ERR, "Failed to retrieve packet from ACS758: " + resp.status_code)

